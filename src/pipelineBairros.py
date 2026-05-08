"""Carregamento padronizado do GeoJSON de bairros do Rio."""
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

from utilsGeo import normalizar_nome_bairro

_ROMAN_VALUES = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
_ROMANO_RE = re.compile(r'^([IVXLCDM]+)\s+', re.IGNORECASE)


def _romano_para_int(romano: str) -> int:
    total, anterior = 0, 0
    for char in reversed(romano.upper()):
        valor = _ROMAN_VALUES[char]
        total += -valor if valor < anterior else valor
        anterior = valor
    return total


def _extrair_codra(regiao_adm_orig: str):
    """Extrai o código numérico da RA do prefixo romano (ex: 'VI LAGOA' -> 6)."""
    m = _ROMANO_RE.match(regiao_adm_orig.strip())
    return _romano_para_int(m.group(1)) if m else None

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
GEOJSON_BAIRROS = RAW / "Limite_de_Bairros.geojson"
IPS_XLSX = RAW / "ips.xlsx"
CENSO_CSV = RAW / "Censo_2022.csv"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

CRS_LATLON = "EPSG:4326"
CRS_METRICO = "EPSG:31983"  # UTM 23S — métrico, padrão IBGE pro Rio

# Paquetá é insular, atendida só por barca (CCR), e o GTFS aqui cobre
# apenas ônibus/BRT/VLT — n_paradas=0 e IPS ausente. Excluímos para evitar
# imputação enganosa; a limitação fica documentada na análise.
BAIRROS_EXCLUIDOS = {'PAQUETA'}


def carregar_bairros() -> gpd.GeoDataFrame:
    """Lê o GeoJSON de bairros e devolve GeoDataFrame padronizado.

    Colunas: bairro, bairro_orig, codbairro, regiao_adm, codra, area_km2, geometry.
    Bairros em BAIRROS_EXCLUIDOS são removidos (ver constante pra justificativa).
    """
    gdf = gpd.read_file(GEOJSON_BAIRROS)

    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(CRS_LATLON)

    gdf['regiao_adm'] = gdf['regiao_adm'].str.strip()
    gdf = gdf.rename(columns={'nome': 'bairro_orig'})
    gdf['bairro'] = gdf['bairro_orig'].map(normalizar_nome_bairro)
    gdf['area_km2'] = gdf.to_crs(CRS_METRICO).geometry.area / 1e6

    gdf = gdf[~gdf['bairro'].isin(BAIRROS_EXCLUIDOS)].reset_index(drop=True)
    gdf = gdf[['bairro', 'bairro_orig', 'codbairro', 'regiao_adm', 'codra',
               'area_km2', 'geometry']]

    assert gdf.crs.to_epsg() == 4326, f"CRS final precisa ser EPSG:4326, veio {gdf.crs}"
    assert gdf['bairro'].is_unique, \
        f"chave 'bairro' tem duplicatas: {gdf[gdf['bairro'].duplicated()]['bairro'].tolist()}"
    assert 160 <= len(gdf) <= 170, f"esperado 160-170 bairros, veio {len(gdf)}"

    return gdf


def fazer_spatial_join_paradas_bairros(
    stops: pd.DataFrame, bairros_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Cruza paradas (stops do GTFS) com polígonos de bairros.

    Retorna GeoDataFrame com uma linha por parada, coluna `bairro` preenchida
    pra paradas dentro do município (NaN pras de fora).
    """
    stops_gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops['stop_lon'], stops['stop_lat']),
        crs=CRS_LATLON,
    )

    assert stops_gdf.crs.to_epsg() == bairros_gdf.crs.to_epsg(), \
        f"CRS divergente: stops={stops_gdf.crs} vs bairros={bairros_gdf.crs}"

    paradas_em_bairros = gpd.sjoin(
        stops_gdf,
        bairros_gdf[['bairro', 'codbairro', 'regiao_adm', 'codra', 'geometry']],
        how='left',
        predicate='within',
    ).drop(columns='index_right')

    return paradas_em_bairros


def carregar_ips_por_ra() -> pd.DataFrame:
    """Lê o IPS por Região Administrativa (aba Plan1 do xlsx do IPP).

    A Plan1 traz 32 RAs com IPS calculado e os indicadores brutos por trás dele.
    Útil pra cruzar com bairros (broadcast por regiao_adm/codra), já que o IPS
    nativamente não desce a nível de bairro.

    Colunas: regiao_adm_norm, regiao_adm_orig, ips, + indicadores brutos.
    """
    df = pd.read_excel(IPS_XLSX, sheet_name='Plan1', engine='openpyxl')
    df = df.rename(columns={'Unnamed: 0': 'regiao_adm_orig', 'IPS': 'ips'})
    df = df.dropna(subset=['regiao_adm_orig', 'ips'])
    df['regiao_adm_norm'] = df['regiao_adm_orig'].map(normalizar_nome_bairro)

    cols_chave = ['regiao_adm_norm', 'regiao_adm_orig', 'ips']
    indicadores = [c for c in df.columns if c not in cols_chave]
    df = df[cols_chave + indicadores].reset_index(drop=True)

    assert 32 <= len(df) <= 33, f"esperado 32-33 RAs, veio {len(df)}"
    assert df['regiao_adm_norm'].is_unique, \
        f"regiao_adm_norm tem duplicatas: {df[df['regiao_adm_norm'].duplicated()]['regiao_adm_norm'].tolist()}"
    assert df['ips'].between(0, 100).all(), "IPS fora do range 0-100"

    return df


def replicar_ips_ra_para_bairros(
    bairros_gdf: gpd.GeoDataFrame, ips_df: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Replica IPS da RA-mãe pros bairros filhos.

    Estratégia 1: merge por codra (chave numérica, mais confiável).
    Estratégia 2: fallback por regiao_adm_norm pros bairros que sobraram.
    """
    ips = ips_df.copy()
    ips['codra'] = ips['regiao_adm_orig'].map(_extrair_codra)

    cols_ips = [c for c in ips.columns
                if c not in ('regiao_adm_orig', 'regiao_adm_norm', 'codra')]

    # estratégia 1: codra
    out = bairros_gdf.merge(ips[['codra'] + cols_ips], on='codra', how='left')

    # estratégia 2 (fallback): nome normalizado da RA
    sem_ips = out['ips'].isna()
    if sem_ips.any():
        ips_por_nome = ips.set_index('regiao_adm_norm')[cols_ips]
        nomes = bairros_gdf.loc[sem_ips, 'regiao_adm'].map(normalizar_nome_bairro)
        for idx, nome_norm in nomes.items():
            if nome_norm in ips_por_nome.index:
                for col in cols_ips:
                    out.at[idx, col] = ips_por_nome.at[nome_norm, col]

    return out


def _stop_to_routes(
    paradas_por_shape: pd.DataFrame, trips_unicos: pd.DataFrame,
) -> pd.DataFrame:
    """Mapeia stop_id -> set de route_ids via shapes que passam perto da parada.

    Aproximação porque o GTFS aqui não traz stop_times. Usa o spatial join
    paradas-shape do parquet interim como proxy de "linhas que servem a parada".
    """
    shape_para_routes = (trips_unicos[['shape_id', 'route_id']]
                         .drop_duplicates()
                         .groupby('shape_id')['route_id']
                         .agg(list))

    expandido = paradas_por_shape.explode('paradas').rename(
        columns={'paradas': 'stop_id'},
    )
    expandido['route_ids'] = expandido['shape_id'].map(shape_para_routes)
    expandido = expandido.dropna(subset=['route_ids']).explode('route_ids').rename(
        columns={'route_ids': 'route_id'},
    )
    return expandido[['stop_id', 'route_id']].drop_duplicates()


def _headway_min_por_trip(frequencies: pd.DataFrame) -> pd.Series:
    """Headway médio por trip (em minutos), ponderado pela duração da janela."""
    f = frequencies[['trip_id', 'start_time', 'end_time', 'headway_secs']].drop_duplicates()
    inicio = pd.to_timedelta(f['start_time']).dt.total_seconds()
    fim = pd.to_timedelta(f['end_time']).dt.total_seconds()
    duracao = (fim - inicio).clip(lower=0)
    f = f.assign(
        duracao=duracao,
        headway_min=f['headway_secs'] / 60.0,
        produto=lambda d: d['headway_min'] * duracao,
    )
    agg = f.groupby('trip_id').agg(produto=('produto', 'sum'),
                                   duracao=('duracao', 'sum'))
    return agg['produto'] / agg['duracao'].replace(0, pd.NA)


def construir_tabela_features_bairros(
    bairros_gdf: gpd.GeoDataFrame,
    paradas_em_bairros: gpd.GeoDataFrame,
    paradas_por_shape: pd.DataFrame,
    trips_unicos: pd.DataFrame,
    frequencies: pd.DataFrame,
    censo: pd.DataFrame,
    ips_df: pd.DataFrame,
    raio_cobertura_m: int = 400,
) -> gpd.GeoDataFrame:
    """Consolida features de Demanda (Censo+IPS) e Oferta (GTFS) por bairro."""
    base = replicar_ips_ra_para_bairros(bairros_gdf, ips_df)[
        ['bairro', 'codbairro', 'regiao_adm', 'codra', 'area_km2', 'ips', 'geometry']
    ]

    # --- DEMANDA (Censo) ---
    pop = censo.rename(columns={
        'Total_de_pessoas_2022': 'populacao',
        'Total_de_domicilios_2022': 'domicilios',
    })[['codbairro', 'populacao', 'domicilios']].copy()
    # codbairro vem como str com zero à esquerda no geojson e int no censo — alinhar
    base['codbairro'] = base['codbairro'].astype(str).str.zfill(3)
    pop['codbairro'] = pop['codbairro'].astype(str).str.zfill(3)
    base = base.merge(pop, on='codbairro', how='left')
    base['densidade_hab_km2'] = base['populacao'] / base['area_km2']

    # --- OFERTA: n_paradas ---
    paradas_validas = paradas_em_bairros[paradas_em_bairros['bairro'].notna()]
    n_paradas = paradas_validas.groupby('bairro').size().rename('n_paradas')
    base = base.merge(n_paradas, on='bairro', how='left')
    base['n_paradas'] = base['n_paradas'].fillna(0).astype(int)

    # --- OFERTA: n_linhas ---
    stop_routes = _stop_to_routes(paradas_por_shape, trips_unicos)
    parada_bairro = paradas_validas[['stop_id', 'bairro']]
    bairro_routes = stop_routes.merge(parada_bairro, on='stop_id', how='inner')
    n_linhas = (bairro_routes.groupby('bairro')['route_id']
                .nunique().rename('n_linhas'))
    base = base.merge(n_linhas, on='bairro', how='left')
    base['n_linhas'] = base['n_linhas'].fillna(0).astype(int)

    # --- OFERTA: headway_medio_min ---
    hw_trip = _headway_min_por_trip(frequencies)
    trip_bairro = (trips_unicos[['trip_id', 'shape_id']]
                   .merge(paradas_por_shape.explode('paradas'),
                          on='shape_id', how='inner')
                   .rename(columns={'paradas': 'stop_id'})
                   .merge(parada_bairro, on='stop_id', how='inner')
                   [['bairro', 'trip_id']]
                   .drop_duplicates())
    trip_bairro['headway_min'] = trip_bairro['trip_id'].map(hw_trip)
    headway = (trip_bairro.dropna(subset=['headway_min'])
               .groupby('bairro')['headway_min'].mean()
               .rename('headway_medio_min'))
    base = base.merge(headway, on='bairro', how='left')

    # --- OFERTA: cobertura_400m ---
    bairros_m = bairros_gdf.to_crs(CRS_METRICO)
    paradas_m = paradas_validas.to_crs(CRS_METRICO)
    buffer_global = paradas_m.geometry.buffer(raio_cobertura_m).union_all()
    cobertura = bairros_m.set_index('bairro').geometry.apply(
        lambda g: g.intersection(buffer_global).area / g.area,
    ).rename('cobertura_400m').clip(0, 1)
    base = base.merge(cobertura, on='bairro', how='left')

    cols_final = ['bairro', 'codbairro', 'regiao_adm', 'codra', 'area_km2',
                  'populacao', 'domicilios', 'densidade_hab_km2', 'ips',
                  'n_paradas', 'n_linhas', 'headway_medio_min', 'cobertura_400m',
                  'geometry']
    return gpd.GeoDataFrame(base[cols_final], geometry='geometry', crs=CRS_LATLON)


def validar_tabela_final(df: gpd.GeoDataFrame) -> None:
    """Sanity checks da tabela final + prints de inspeção."""
    print(f'\nLinhas: {len(df)} | Colunas: {len(df.columns)}')
    print(f'NaN por coluna:')
    nans = df.isna().sum()
    print(nans[nans > 0].to_string() if nans.sum() else '  (nenhum)')

    print('\nEstatísticas das features numéricas:')
    feats = ['populacao', 'domicilios', 'densidade_hab_km2', 'ips',
             'n_paradas', 'n_linhas', 'headway_medio_min', 'cobertura_400m']
    print(df[feats].agg(['median', 'min', 'max']).round(2).to_string())

    print('\nTop 10 n_paradas:')
    print(df.nlargest(10, 'n_paradas')[['bairro', 'n_paradas', 'n_linhas']].to_string(index=False))
    print('\nBottom 10 n_paradas (com cobertura > 0):')
    print(df[df['n_paradas'] > 0].nsmallest(10, 'n_paradas')
          [['bairro', 'n_paradas', 'cobertura_400m']].to_string(index=False))
    print('\nTop 10 cobertura_400m:')
    print(df.nlargest(10, 'cobertura_400m')[['bairro', 'cobertura_400m']].to_string(index=False))
    print('\nBottom 10 cobertura_400m:')
    print(df.nsmallest(10, 'cobertura_400m')[['bairro', 'cobertura_400m']].to_string(index=False))

    assert 160 <= len(df) <= 170, f'esperado 160-170 bairros, veio {len(df)}'
    assert df['n_paradas'].sum() > 5000, \
        f'soma n_paradas muito baixa: {df["n_paradas"].sum()}'
    assert df['cobertura_400m'].between(0, 1).all(), \
        'cobertura_400m fora do range [0, 1]'


if __name__ == '__main__':
    bairros = carregar_bairros()
    print(f'Bairros carregados: {len(bairros)}')
    print(f'CRS: {bairros.crs}')
    print(f'Colunas: {list(bairros.columns)}')
    print(f'Soma de area_km2: {bairros["area_km2"].sum():,.1f} km²')

    print('\nTop 5 maiores em area_km2:')
    print(bairros.nlargest(5, 'area_km2')[['bairro', 'area_km2']].to_string(index=False))

    print('\n=== Spatial join paradas → bairros ===')
    from pipelineDados import stops
    paradas_em_bairros = fazer_spatial_join_paradas_bairros(stops, bairros)

    n_total = len(paradas_em_bairros)
    n_dentro = paradas_em_bairros['bairro'].notna().sum()
    pct = 100 * n_dentro / n_total
    print(f'Paradas total: {n_total:,}')
    print(f'Paradas dentro do município: {n_dentro:,} ({pct:.1f}%)')

    assert pct >= 95, f'cobertura abaixo de 95%: {pct:.1f}%'

    print('\nTop 10 bairros com mais paradas:')
    top10 = paradas_em_bairros['bairro'].value_counts().head(10)
    print(top10.to_string())

    INTERIM.mkdir(parents=True, exist_ok=True)
    out = INTERIM / 'paradas_em_bairros.parquet'
    paradas_em_bairros.to_parquet(out)
    print(f'\nSalvo: {out.relative_to(ROOT)}')

    print('\n=== IPS por RA (aba Plan1) ===')
    ips = carregar_ips_por_ra()
    print(f'RAs com IPS: {len(ips)}')
    print(f'IPS médio: {ips["ips"].mean():.2f}')
    print(f'IPS min/max: {ips["ips"].min():.2f} / {ips["ips"].max():.2f}')
    print(f'Colunas: {len(ips.columns)} (3 chave + {len(ips.columns)-3} indicadores)')

    print('\nTop 3 IPS:')
    print(ips.nlargest(3, 'ips')[['regiao_adm_norm', 'ips']].to_string(index=False))
    print('\nBottom 3 IPS:')
    print(ips.nsmallest(3, 'ips')[['regiao_adm_norm', 'ips']].to_string(index=False))

    print('\n=== Replicação IPS RA → bairros ===')
    bairros_ips = replicar_ips_ra_para_bairros(bairros, ips)
    n_total = len(bairros_ips)
    n_com = bairros_ips['ips'].notna().sum()
    n_sem = n_total - n_com
    pct = 100 * n_com / n_total
    print(f'Bairros com IPS: {n_com}/{n_total} ({pct:.1f}%)')

    assert pct >= 95, f'cobertura abaixo de 95%: {pct:.1f}%'

    if n_sem:
        sem = bairros_ips[bairros_ips['ips'].isna()]
        print(f'\nBairros sem IPS ({n_sem}):')
        print(sem[['bairro', 'regiao_adm', 'codra']].head(10).to_string(index=False))

    print('\n=== Construindo tabela final de features ===')
    from pipelineDados import frequencies, trips_unicos
    paradas_por_shape = pd.read_parquet(INTERIM / 'paradas_por_shape.parquet')
    censo = pd.read_csv(CENSO_CSV)

    features = construir_tabela_features_bairros(
        bairros_gdf=bairros,
        paradas_em_bairros=paradas_em_bairros,
        paradas_por_shape=paradas_por_shape,
        trips_unicos=trips_unicos,
        frequencies=frequencies,
        censo=censo,
        ips_df=ips,
    )

    validar_tabela_final(features)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    features.to_parquet(PROCESSED / 'bairros_features.parquet')
    features.to_file(PROCESSED / 'bairros_features.geojson', driver='GeoJSON')
    print(f'\nSalvo: data/processed/bairros_features.parquet')
    print(f'Salvo: data/processed/bairros_features.geojson')
