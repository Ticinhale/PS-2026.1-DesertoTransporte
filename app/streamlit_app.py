"""
DTI-Rio — Streamlit App
Protótipo interativo do Índice de Deserto de Transporte do Rio de Janeiro
"""

import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium


# Configuração da página
st.set_page_config(
    page_title="DTI-Rio | Índice de Deserto de Transporte",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Tipologia dos bairros (resultado do K-Means com k=6 — notebooks/modelagem.ipynb)
NOMES_CLUSTERS = {
    0: "Periferia Densa Urbana",
    1: "Bairros Privilegiados",
    2: "Periferia Territorial Vulnerável",
    3: "Desertos Sociais Críticos",
    4: "Hubs de Linhas Estratégicos",
    5: "Megabairros de Corredor",
}

CORES_CLUSTERS = {
    0: "#3498db",  # azul
    1: "#f1c40f",  # amarelo
    2: "#2ecc71",  # verde
    3: "#e74c3c",  # vermelho
    4: "#9b59b6",  # roxo
    5: "#1abc9c",  # ciano
}

DESCRICOES_CLUSTERS = {
    0: (
        "Periferia consolidada do subúrbio carioca: alta densidade populacional, "
        "**boa cobertura espacial de paradas (≈92%)**, mas IPS baixo. O DTI fica em patamar "
        "médio porque a oferta existe — o que pesa é a vulnerabilidade social acumulada."
    ),
    1: (
        "Bairros tradicionais bem servidos (Zona Sul, Tijuca, Vila Isabel): "
        "**maior IPS (≈84)** e cobertura alta. DTI mais baixo do município — "
        "referência de equilíbrio oferta/demanda."
    ),
    2: (
        "Extremos territoriais e enclaves isolados (Gericinó, Grumari, Complexo do Alemão): "
        "**baixa cobertura espacial (≈49%)** e baixa densidade. O deserto aqui é geográfico — "
        "áreas mal alcançadas pela rede convencional."
    ),
    3: (
        "Bairros com **DTI mais alto do município (≈59)**: Rocinha, Acari, Costa Barros, Pavuna. "
        "Combinam alta densidade, IPS muito baixo e cobertura razoável — o transporte chega, "
        "mas a vulnerabilidade estrutural domina o índice."
    ),
    4: (
        "Hubs centrais e corredores com **alta diversidade de linhas (≈142 linhas)**: "
        "Maré, Centro, Lapa, Vasco da Gama. Cobertura quase total e boa conectividade — "
        "papel sistêmico na rede."
    ),
    5: (
        "Megabairros do oeste (Santa Cruz, Bangu, Realengo, Jacarepaguá, Guaratiba): "
        "**número absoluto enorme de paradas (≈283)** mas dispersas em áreas gigantes — "
        "cobertura efetiva baixa (≈40%) apesar do volume de infraestrutura."
    ),
}


# Carregamento de dados
@st.cache_data
def carregar_dados():
    """Carrega o parquet final do pipeline (com clusters da modelagem)."""
    df = gpd.read_parquet("data/processed/bairros_dti_clusters.parquet")
    df = df.set_crs("EPSG:4326")

    # Tratar NaN no headway (apenas GRUMARI e GERICINÓ)
    df["headway_medio_min"] = df["headway_medio_min"].fillna(0)

    # Calcular paradas_por_km2 caso não esteja no parquet
    if "paradas_por_km2" not in df.columns:
        df["paradas_por_km2"] = df["n_paradas"] / df["area_km2"]

    # Aplicar nomes dos clusters
    df["nome_cluster"] = df["cluster"].map(NOMES_CLUSTERS)

    return df



# Header
st.title("🚌 DTI-Rio")
st.markdown("##### Índice de Deserto de Transporte do Rio de Janeiro")
st.markdown(
    "Identifica bairros onde a oferta de transporte público é insuficiente "
    "frente à demanda da população: combinando densidade, vulnerabilidade "
    "social (IPS) e cobertura espacial de paradas."
)

df = carregar_dados()


# Sidebar 
with st.sidebar:
    st.markdown("### 📊 Sobre o projeto")
    st.markdown(
        "**DTI-Rio** é um índice composto (0–100) calculado para os "
        "164 bairros do município do Rio de Janeiro."
    )
    
    st.markdown("### 📈 Estatísticas gerais")
    col1, col2 = st.columns(2)
    col1.metric("Bairros analisados", len(df))
    col2.metric("DTI médio", f"{df['DTI'].mean():.1f}")
    
    col1.metric("Total de paradas", f"{df['n_paradas'].sum():,}")
    col2.metric("População total", f"{df['populacao'].sum()/1_000_000:.1f}M")
    
    st.markdown("### 🎨 Interpretação")
    st.markdown(
        "- 🟢 **DTI baixo** (< 38) — bem servido\n"
        "- 🟡 **DTI médio** (38–52) — equilíbrio\n"
        "- 🟠 **DTI alto** (52–60) — atenção\n"
        "- 🔴 **DTI crítico** (> 60) — deserto"
    )
    
    st.markdown("---")
    st.caption("UFRJ Analytica — Hackathon 2026.1")
    st.caption("Grupo H — Letícia, Júlio, Luiza, Camila")



# Abas principais
aba1, aba2, aba3, aba4 = st.tabs([
    "🗺️ Mapa Interativo",
    "📋 Ranking dos Desertos",
    "🔮 Simulador de Intervenção",
    "🎯 Tipologia dos Bairros",
])


# ABA 1 — MAPA INTERATIVO
with aba1:
    st.markdown("### Mapa coroplético do DTI por bairro")
    st.markdown(
        "Passe o mouse sobre os bairros para ver detalhes. "
        "**Quanto mais vermelho, maior o DTI** (mais deserto)."
    )
    
    centro_rio = [-22.91, -43.40]
    
    m = folium.Map(
        location=centro_rio,
        zoom_start=11,
        tiles="cartodbpositron",
    )
    
    folium.Choropleth(
        geo_data=df.__geo_interface__,
        name="DTI",
        data=df,
        columns=["bairro", "DTI"],
        key_on="feature.properties.bairro",
        fill_color="RdYlGn_r",
        fill_opacity=0.7,
        line_opacity=0.3,
        legend_name="DTI — 0 = bem servido | 100 = deserto crítico",
        nan_fill_color="lightgrey",
        nan_fill_opacity=0.4,
        bins=[26, 38, 46, 52, 60, 80],
    ).add_to(m)
    
    folium.GeoJson(
        df,
        style_function=lambda x: {"fillOpacity": 0, "color": "transparent"},
        tooltip=folium.GeoJsonTooltip(
            fields=["bairro", "regiao_adm", "DTI", "ips", "cobertura_400m", "n_paradas"],
            aliases=["Bairro:", "Região Adm:", "DTI:", "IPS:", "Cobertura 400m:", "Nº de paradas:"],
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: white;
                border: 1px solid grey;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
            """,
        ),
    ).add_to(m)
    
    st_folium(m, width=None, height=600, returned_objects=[])
    
    with st.expander("ℹ️ Como interpretar este mapa"):
        st.markdown(
            "O DTI combina **Demanda** (densidade demográfica + vulnerabilidade social via IPS invertido) "
            "com **Oferta** (densidade de paradas, cobertura espacial em 400m, número de linhas, headway médio). "
            "Bairros em vermelho intenso podem indicar 3 tipos de deserto:\n\n"
            "1. **Sociais densos** — alta densidade + IPS baixo (ex: Rocinha, Maré)\n"
            "2. **Territoriais** — baixa cobertura em áreas rurais (ex: Santa Cruz, Guaratiba)\n"
            "3. **Técnicos** — áreas restritas sem ônibus convencional (ex: Gericinó, Grumari)"
        )


# ABA 2 — RANKING
with aba2:
    st.markdown("### Ranking dos bairros por DTI")
    st.markdown(
        "Use os filtros para explorar os bairros por região administrativa, "
        "nível de DTI ou características específicas."
    )
    
    #  Filtros lado a lado 
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        regioes = ["Todas"] + sorted(df["regiao_adm"].unique().tolist())
        regiao_sel = st.selectbox("📍 Região Administrativa", regioes)
    
    with col_f2:
        nivel_dti = st.selectbox(
            "🚦 Nível de DTI",
            ["Todos", "Crítico (>60)", "Alto (52-60)", "Médio (38-52)", "Baixo (<38)"],
        )
    
    with col_f3:
        ordenacao = st.selectbox(
            "📊 Ordenar por",
            ["DTI (maior primeiro)", "DTI (menor primeiro)", 
             "População (maior primeiro)", "Cobertura 400m (menor primeiro)"],
        )
    
    #  Aplicar filtros 
    df_filtrado = df.copy()
    
    if regiao_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado["regiao_adm"] == regiao_sel]
    
    if nivel_dti == "Crítico (>60)":
        df_filtrado = df_filtrado[df_filtrado["DTI"] > 60]
    elif nivel_dti == "Alto (52-60)":
        df_filtrado = df_filtrado[(df_filtrado["DTI"] > 52) & (df_filtrado["DTI"] <= 60)]
    elif nivel_dti == "Médio (38-52)":
        df_filtrado = df_filtrado[(df_filtrado["DTI"] > 38) & (df_filtrado["DTI"] <= 52)]
    elif nivel_dti == "Baixo (<38)":
        df_filtrado = df_filtrado[df_filtrado["DTI"] <= 38]
    
    # Ordenação
    if ordenacao == "DTI (maior primeiro)":
        df_filtrado = df_filtrado.sort_values("DTI", ascending=False)
    elif ordenacao == "DTI (menor primeiro)":
        df_filtrado = df_filtrado.sort_values("DTI", ascending=True)
    elif ordenacao == "População (maior primeiro)":
        df_filtrado = df_filtrado.sort_values("populacao", ascending=False, na_position="last")
    elif ordenacao == "Cobertura 400m (menor primeiro)":
        df_filtrado = df_filtrado.sort_values("cobertura_400m", ascending=True)
    
    #  Indicadores rápidos do filtro aplicado 
    st.markdown("---")
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Bairros listados", len(df_filtrado))
    col_k2.metric("DTI médio do filtro", f"{df_filtrado['DTI'].mean():.1f}")
    col_k3.metric("População total", f"{df_filtrado['populacao'].sum()/1_000:.0f}k")
    col_k4.metric("Paradas total", f"{df_filtrado['n_paradas'].sum():,}")
    
    #  Tabela 
    st.markdown("---")
    
    # Selecionar e renomear colunas pra exibição
    tabela = df_filtrado[[
        "bairro", "regiao_adm", "DTI", "ips", 
        "populacao", "densidade_hab_km2",
        "n_paradas", "cobertura_400m",
    ]].copy()
    
    tabela.columns = [
        "Bairro", "Região Adm", "DTI", "IPS",
        "População", "Densidade (hab/km²)",
        "Nº Paradas", "Cobertura 400m",
    ]
    
    # Formatar números
    tabela["DTI"] = tabela["DTI"].round(1)
    tabela["IPS"] = tabela["IPS"].round(1)
    
    # Formatar densidade com separador de milhar (49328 → 49.328)
    tabela["Densidade (hab/km²)"] = tabela["Densidade (hab/km²)"].apply(
        lambda x: f"{x:,.0f}".replace(",", ".") if pd.notna(x) else "—"
    )
    
    # Formatar população com separador de milhar
    tabela["População"] = tabela["População"].apply(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notna(x) else "—"
    )
    
    tabela["Cobertura 400m"] = (df_filtrado["cobertura_400m"] * 100).round(1).astype(str) + "%"
    
    # Exibir
    st.dataframe(
        tabela,
        use_container_width=True,
        hide_index=True,
        column_config={
            "DTI": st.column_config.NumberColumn(
                "DTI",
                help="Índice de Deserto de Transporte (0-100)",
                format="%.1f",
            ),
            "População": st.column_config.NumberColumn(
                format="%d",
            ),
        },
        height=500,
    )
    
    #  Download 
    csv_data = tabela.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Baixar tabela em CSV",
        data=csv_data,
        file_name=f"dti_rio_ranking_{regiao_sel.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )



# ABA 3 — SIMULADOR DE INTERVENÇÃO
with aba3:
    st.markdown("### Simulador de Intervenção")
    st.markdown(
        "Selecione um bairro e ajuste as variáveis de **oferta de transporte** "
        "para simular o impacto de intervenções no DTI."
    )
    
    #  Seleção do bairro 
    bairros_ordenados = df.sort_values("DTI", ascending=False)
    
    bairro_selecionado = st.selectbox(
        "🏙️ Selecione um bairro",
        bairros_ordenados["bairro"].tolist(),
        index=0,
    )
    
    bairro_data = df[df["bairro"] == bairro_selecionado].iloc[0]
    
    #  Indicadores atuais 
    st.markdown("---")
    st.markdown(f"#### 📊 Situação atual: {bairro_data['bairro']}")
    
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    col_a1.metric("DTI atual", f"{bairro_data['DTI']:.1f}")
    col_a2.metric("IPS", f"{bairro_data['ips']:.1f}")
    col_a3.metric("Densidade", f"{bairro_data['densidade_hab_km2']:,.0f} hab/km²")
    pop_str = f"{int(bairro_data['populacao']):,}".replace(",", ".") if pd.notna(bairro_data['populacao']) else "—"
    col_a4.metric("População", pop_str)
    
    #  Sliders de intervenção 
    st.markdown("---")
    st.markdown("#### 🎛️ Ajustes de Oferta (intervenção simulada)")
    
    # Tratar headway: se for 0 ou NaN, usar 30 como padrão pro slider
    headway_atual = float(bairro_data["headway_medio_min"]) if bairro_data["headway_medio_min"] > 0 else 30.0
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        nova_cobertura = st.slider(
            "Cobertura espacial (raio 400m)",
            min_value=0.0,
            max_value=1.0,
            value=float(bairro_data["cobertura_400m"]),
            step=0.05,
            help="Fração da área do bairro a até 400m de uma parada",
        )
        
        novas_paradas = st.slider(
            "Nº de paradas",
            min_value=0,
            max_value=int(df["n_paradas"].max()),
            value=int(bairro_data["n_paradas"]),
            step=5,
        )
    
    with col_s2:
        novo_headway = st.slider(
            "Headway médio (min)",
            min_value=5.0,
            max_value=60.0,
            value=headway_atual,
            step=1.0,
            help="Intervalo médio entre veículos (menor = melhor)",
        )
        
        novas_linhas = st.slider(
            "Nº de linhas distintas",
            min_value=0,
            max_value=int(df["n_linhas"].max()),
            value=int(bairro_data["n_linhas"]),
            step=5,
        )
    
    # CÁLCULO SIMPLIFICADO DO NOVO DTI (CALIBRADO)
    
    # Variação ABSOLUTA da cobertura (já está em 0-1)
    delta_cobertura = nova_cobertura - bairro_data["cobertura_400m"]
    
    # Variações PERCENTUAIS limitadas (cap em ±100% pra evitar amplificação)
    paradas_orig = max(bairro_data["n_paradas"], 1)
    delta_paradas = (novas_paradas - bairro_data["n_paradas"]) / paradas_orig
    delta_paradas = max(-1, min(1, delta_paradas))  # cap em ±100%
    
    headway_orig = max(headway_atual, 1)
    delta_headway = (headway_atual - novo_headway) / headway_orig
    delta_headway = max(-1, min(1, delta_headway))
    
    linhas_orig = max(bairro_data["n_linhas"], 1)
    delta_linhas = (novas_linhas - bairro_data["n_linhas"]) / linhas_orig
    delta_linhas = max(-1, min(1, delta_linhas))
    
    # Pesos das features (cobertura tem peso maior - é a feature principal)
    PESO_COBERTURA = 0.40   # principal
    PESO_PARADAS = 0.15     # complementar
    PESO_HEADWAY = 0.30     # importante
    PESO_LINHAS = 0.15      # complementar
    
    # Sensibilidade total: máximo de 12 pontos de DTI muda quando todas
    # as features de oferta vão de 0% a 100% (ou vice-versa)
    SENSIBILIDADE = 12
    
    # Como cobertura já é 0-1, usar direto. Outros são percentuais
    impacto = (
        delta_cobertura * PESO_COBERTURA +
        delta_paradas * PESO_PARADAS +
        delta_headway * PESO_HEADWAY +
        delta_linhas * PESO_LINHAS
    ) * SENSIBILIDADE
    
    novo_dti = bairro_data["DTI"] - impacto
    novo_dti = max(0, min(100, novo_dti))
    
    delta_dti = novo_dti - bairro_data["DTI"]
    
    #  Resultado da simulação 
    st.markdown("---")
    st.markdown("#### 🎯 Resultado da simulação")
    
    col_r1, col_r2, col_r3 = st.columns(3)
    
    col_r1.metric(
        "DTI atual", 
        f"{bairro_data['DTI']:.1f}",
    )
    col_r2.metric(
        "DTI simulado", 
        f"{novo_dti:.1f}",
        delta=f"{delta_dti:+.1f}",
        delta_color="inverse",
    )
    col_r3.metric(
        "Variação", 
        f"{delta_dti:+.1f} pontos",
    )
    
    # Interpretação
    if novo_dti < 38:
        st.success(
            f"✅ **Intervenção transformadora.** O bairro saiu da categoria de deserto "
            f"e passou a ser considerado bem servido (DTI < 38)."
        )
    elif novo_dti < 52 and bairro_data["DTI"] >= 52:
        st.success(
            f"✅ **Intervenção significativa.** O bairro saiu da categoria de deserto "
            f"e atingiu o equilíbrio (DTI < 52)."
        )
    elif novo_dti < 60 and bairro_data["DTI"] >= 60:
        st.info(
            f"👍 **Melhoria importante.** O bairro saiu da categoria crítica, mas "
            f"ainda é considerado em alerta (DTI 52-60)."
        )
    elif delta_dti < -3:
        st.info(
            f"👍 **Melhoria moderada.** Reduziu {abs(delta_dti):.1f} pontos no DTI, "
            f"mas o bairro permanece na mesma categoria."
        )
    elif delta_dti < 0:
        st.warning(
            f"⚠️ **Pouco impacto.** A intervenção atual gera mudança marginal."
        )
    else:
        st.error(
            f"❌ **Intervenção piorou o DTI.** Reduzir oferta aumenta o índice."
        )
    
    if bairro_data["ips"] < 50 and nova_cobertura > 0.9:
        st.info(
            "💡 **Informação:** mesmo com cobertura quase total, o DTI deste bairro permanece "
            "elevado por causa da combinação de **alta densidade demográfica** e **IPS baixo**. "
            "**O DTI captura desigualdade estrutural, não só falta de transporte** — essa é a "
            "principal mensagem do projeto."
        )
    
    #  Aviso técnico
    with st.expander("⚠️ Sobre a precisão desta simulação"):
        st.markdown(
            "O cálculo de DTI simulado é uma **aproximação direcional** baseada na variação "
            "proporcional das features de Oferta em relação aos valores originais do bairro. "
            "Para o cálculo exato do DTI seria necessário re-rodar o pipeline completo de "
            "normalização contra os 164 bairros, o que não é possível em tempo real. "
            "**O simulador serve para explorar tendências, não como ferramenta de planejamento operacional.**"
        )


# ABA 4 — TIPOLOGIA DOS BAIRROS (K-MEANS)
with aba4:
    st.markdown("### Tipologia dos bairros do Rio")
    st.markdown(
        "Aplicação de **K-Means (k=6)** sobre as features de oferta e demanda "
        "(densidade, IPS, paradas, cobertura, linhas, headway) revela **6 perfis distintos** "
        "de bairros. A tipologia mostra que o DTI alto não tem uma única causa: pode ser "
        "vulnerabilidade social, isolamento territorial ou sobrecarga de demanda."
    )

    #  Mapa colorido por cluster
    st.markdown("---")
    st.markdown("#### 🗺️ Mapa da tipologia")

    centro_rio_t = [-22.91, -43.40]
    m_cluster = folium.Map(
        location=centro_rio_t,
        zoom_start=11,
        tiles="cartodbpositron",
    )

    for cluster_id, nome in NOMES_CLUSTERS.items():
        sub = df[df["cluster"] == cluster_id]
        cor = CORES_CLUSTERS[cluster_id]
        folium.GeoJson(
            sub,
            name=f"{cluster_id} — {nome}",
            style_function=lambda _x, cor=cor: {
                "fillColor": cor,
                "color": "white",
                "weight": 0.5,
                "fillOpacity": 0.75,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["bairro", "regiao_adm", "nome_cluster", "DTI", "ips", "cobertura_400m"],
                aliases=["Bairro:", "Região Adm:", "Tipologia:", "DTI:", "IPS:", "Cobertura 400m:"],
                localize=True,
                sticky=False,
                style="""
                    background-color: white;
                    border: 1px solid grey;
                    border-radius: 3px;
                    padding: 6px;
                    font-size: 12px;
                """,
            ),
        ).add_to(m_cluster)

    folium.LayerControl(collapsed=False).add_to(m_cluster)
    st_folium(m_cluster, width=None, height=600, returned_objects=[])

    # Legenda lado a lado
    st.markdown("**Legenda:**")
    legend_cols = st.columns(3)
    for i, (cid, nome) in enumerate(NOMES_CLUSTERS.items()):
        n_b = (df["cluster"] == cid).sum()
        with legend_cols[i % 3]:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"
                f"<span style='display:inline-block;width:14px;height:14px;background:{CORES_CLUSTERS[cid]};"
                f"border-radius:3px;border:1px solid #ccc;'></span>"
                f"<span><b>{cid}</b> — {nome} ({n_b})</span></div>",
                unsafe_allow_html=True,
            )

    #  Tabela de perfis
    st.markdown("---")
    st.markdown("#### 📊 Perfis comparativos dos clusters")
    st.markdown(
        "Médias de cada feature por cluster — útil pra entender o que diferencia cada perfil."
    )

    perfis = df.groupby("cluster").agg(
        n_bairros=("bairro", "count"),
        DTI_medio=("DTI", "mean"),
        IPS_medio=("ips", "mean"),
        densidade=("densidade_hab_km2", "mean"),
        n_paradas=("n_paradas", "mean"),
        cobertura=("cobertura_400m", "mean"),
        headway=("headway_medio_min", "mean"),
        n_linhas=("n_linhas", "mean"),
    ).round(1)
    perfis.insert(0, "Tipologia", perfis.index.map(NOMES_CLUSTERS))
    perfis = perfis.rename(columns={
        "n_bairros": "Nº bairros",
        "DTI_medio": "DTI",
        "IPS_medio": "IPS",
        "densidade": "Densidade (hab/km²)",
        "n_paradas": "Paradas",
        "cobertura": "Cobertura 400m",
        "headway": "Headway (min)",
        "n_linhas": "Linhas",
    })

    st.dataframe(
        perfis,
        use_container_width=True,
        column_config={
            "Cobertura 400m": st.column_config.ProgressColumn(
                "Cobertura 400m",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "Densidade (hab/km²)": st.column_config.NumberColumn(format="%.0f"),
        },
    )

    #  Drill-down por cluster
    st.markdown("---")
    st.markdown("#### 🔎 Análise detalhada por tipologia")

    cluster_sel = st.selectbox(
        "Selecione uma tipologia",
        options=list(NOMES_CLUSTERS.keys()),
        format_func=lambda c: f"{c} — {NOMES_CLUSTERS[c]}",
    )

    sub = df[df["cluster"] == cluster_sel].sort_values("DTI", ascending=False)
    cor_sel = CORES_CLUSTERS[cluster_sel]

    st.markdown(
        f"<div style='border-left:6px solid {cor_sel};padding:12px 16px;"
        f"background:rgba(255,255,255,0.05);"
        f"border-radius:4px;margin:12px 0;'>"
        f"<h4 style='margin:0 0 6px 0;color:inherit;'>{cluster_sel} — {NOMES_CLUSTERS[cluster_sel]}</h4>"
        f"<p style='margin:0;color:inherit;'>{DESCRICOES_CLUSTERS[cluster_sel]}</p></div>",
        unsafe_allow_html=True,
    )

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Nº de bairros", len(sub))
    col_m2.metric("DTI médio", f"{sub['DTI'].mean():.1f}")
    col_m3.metric("IPS médio", f"{sub['ips'].mean():.1f}")
    col_m4.metric("Cobertura 400m média", f"{sub['cobertura_400m'].mean()*100:.0f}%")

    st.markdown("**Bairros desta tipologia (ordenados por DTI):**")
    tabela_cluster = sub[[
        "bairro", "regiao_adm", "DTI", "ips",
        "cobertura_400m", "n_paradas", "n_linhas",
    ]].copy()
    tabela_cluster.columns = [
        "Bairro", "Região Adm", "DTI", "IPS",
        "Cobertura 400m", "Nº Paradas", "Nº Linhas",
    ]
    tabela_cluster["DTI"] = tabela_cluster["DTI"].round(1)
    tabela_cluster["IPS"] = tabela_cluster["IPS"].round(1)
    tabela_cluster["Cobertura 400m"] = (sub["cobertura_400m"].astype(float) * 100).round(1)

    st.dataframe(
        tabela_cluster,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cobertura 400m": st.column_config.ProgressColumn(
                "Cobertura 400m (%)",
                min_value=0.0,
                max_value=100.0,
                format="%.1f%%",
            ),
        },
        height=min(500, 60 + 35 * len(sub)),
    )

    with st.expander("ℹ️ Como a tipologia foi construída"):
        st.markdown(
            "**Algoritmo:** K-Means (scikit-learn) com `k=6`, `random_state=42`, `n_init=10`.\n\n"
            "**Features padronizadas** (StandardScaler) usadas no clustering:\n"
            "- `densidade_hab_km2` — demanda demográfica\n"
            "- `ips` — vulnerabilidade social (Índice de Progresso Social)\n"
            "- `n_paradas`, `paradas_por_km2` — oferta absoluta e densidade\n"
            "- `n_linhas` — diversidade da rede\n"
            "- `cobertura_400m` — distribuição espacial das paradas\n"
            "- `headway_medio_min` — frequência média de veículos\n\n"
            "**Escolha de k=6** — combinação do método do cotovelo + silhouette score, "
            "balanceando interpretabilidade e poder discriminatório.\n\n"
            "**Leitura central:** o DTI é um índice contínuo, mas a tipologia mostra que "
            "bairros com DTI parecido podem ter **causas diferentes** (vulnerabilidade social vs. "
            "isolamento territorial vs. sobrecarga de demanda) — e portanto exigem **intervenções diferentes**."
        )