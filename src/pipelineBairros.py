"""Carregamento padronizado do GeoJSON de bairros do Rio."""
from pathlib import Path

import geopandas as gpd
import pandas as pd

from utilsGeo import normalizar_nome_bairro

ROOT = Path(__file__).resolve().parent.parent
GEOJSON_BAIRROS = ROOT / "data" / "raw" / "Limite_de_Bairros.geojson"
IPS_XLSX = ROOT / "data" / "raw" / "ips.xlsx"
INTERIM = ROOT / "data" / "interim"

CRS_LATLON = "EPSG:4326"
CRS_METRICO = "EPSG:31983"  # UTM 23S — métrico, padrão IBGE pro Rio


def carregar_bairros() -> gpd.GeoDataFrame:
    """Lê o GeoJSON de bairros e devolve GeoDataFrame padronizado.

    Colunas: bairro, bairro_orig, codbairro, regiao_adm, codra, area_km2, geometry
    """
    gdf = gpd.read_file(GEOJSON_BAIRROS)

    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(CRS_LATLON)

    gdf['regiao_adm'] = gdf['regiao_adm'].str.strip()
    gdf = gdf.rename(columns={'nome': 'bairro_orig'})
    gdf['bairro'] = gdf['bairro_orig'].map(normalizar_nome_bairro)
    gdf['area_km2'] = gdf.to_crs(CRS_METRICO).geometry.area / 1e6

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
