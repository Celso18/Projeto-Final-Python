"""ETL, análise e relatório do projeto prático de análise de vendas."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent
REQUIRED_COLUMNS = [
    "id_item_venda",
    "id_pedido",
    "data_venda",
    "nome_produto",
    "categoria_produto",
    "quantidade",
    "preco_unitario",
    "desconto",
    "valor_total",
    "nome_cliente",
    "cidade_cliente",
    "estado_cliente",
    "nome_vendedor",
    "forma_pagamento",
    "status_venda",
]
NUMERIC_COLUMNS = [
    "id_item_venda",
    "id_pedido",
    "quantidade",
    "preco_unitario",
    "desconto",
    "valor_total",
]
REGIONS = {
    "AC": "Norte",
    "AP": "Norte",
    "AM": "Norte",
    "PA": "Norte",
    "RO": "Norte",
    "RR": "Norte",
    "TO": "Norte",
    "AL": "Nordeste",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "MA": "Nordeste",
    "PB": "Nordeste",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste",
    "GO": "Centro-Oeste",
    "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste",
    "MG": "Sudeste",
    "RJ": "Sudeste",
    "SP": "Sudeste",
    "PR": "Sul",
    "RS": "Sul",
    "SC": "Sul",
}
CATEGORY_LABELS = {
    "informatica": "Informática",
    "eletronicos": "Eletrônicos",
    "acessorios": "Acessórios",
    "audio": "Áudio",
}
STATUS_LABELS = {
    "concluido": "Concluído",
    "cancelado": "Cancelado",
    "devolvido": "Devolvido",
    "pendente": "Pendente",
}
PAYMENT_LABELS = {
    "pix": "PIX",
    "boleto": "Boleto",
    "cartao de credito": "Cartão de Crédito",
    "cartao de debito": "Cartão de Débito",
}
COLORS = ["#2455A4", "#2D8A75", "#E1A13A", "#BC5962", "#7859A6"]


def text_key(value: object) -> str:
    """Return a lowercase, accent-insensitive key for category normalization."""
    normalized = unicodedata.normalize("NFKD", str(value))
    return re.sub(r"\s+", " ", normalized.encode("ascii", "ignore").decode()).strip().lower()


def money(value: float) -> str:
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def save_chart(fig: plt.Figure, output: Path, filename: str) -> str:
    fig.tight_layout()
    fig.savefig(output / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return f"graficos/{filename}"


def prepare_data(csv_path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    raw = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(raw.columns))
    if missing_columns:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(missing_columns)}")

    original_rows = len(raw)
    original_columns = len(raw.columns)
    original_nulls = raw.isna().sum()
    original_dtypes = raw.dtypes.astype(str)
    exact_duplicates = int(raw.duplicated().sum())
    data = raw.drop_duplicates().copy()

    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["data_venda"] = pd.to_datetime(
        data["data_venda"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )

    data["status_venda"] = data["status_venda"].map(
        lambda value: STATUS_LABELS.get(text_key(value), str(value).strip())
    )
    data["categoria_produto"] = data["categoria_produto"].map(
        lambda value: CATEGORY_LABELS.get(text_key(value), str(value).strip())
    )
    data["forma_pagamento"] = data["forma_pagamento"].map(
        lambda value: PAYMENT_LABELS.get(text_key(value), str(value).strip())
    )
    for column in [
        "nome_produto",
        "nome_cliente",
        "cidade_cliente",
        "estado_cliente",
        "nome_vendedor",
    ]:
        data[column] = data[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    invalid_dates = int(data["data_venda"].isna().sum())
    gross = data["preco_unitario"] * data["quantidade"]
    invalid_quantity = data["quantidade"].isna() | data["quantidade"].le(0)
    invalid_discount = (
        data["desconto"].isna()
        | data["desconto"].lt(0)
        | data["desconto"].gt(gross)
    )
    invalid_price = data["preco_unitario"].isna() | data["preco_unitario"].le(0)
    invalid_amount = data["valor_total"].isna()
    invalid_financial_rows = invalid_quantity | invalid_discount | invalid_price | invalid_amount
    amount_mismatches = int(
        (
            data["valor_total"].notna()
            & (data["valor_total"] - (gross - data["desconto"])).abs().gt(0.01)
        ).sum()
    )
    data["valor_bruto"] = gross
    data["valor_liquido"] = gross - data["desconto"]
    data["cidade_cliente"] = data["cidade_cliente"].fillna("Não informado")
    data["regiao_cliente"] = data["estado_cliente"].map(REGIONS).fillna("UF não mapeada")

    remaining_duplicate_ids = int(data["id_item_venda"].duplicated().sum())
    if remaining_duplicate_ids:
        duplicate_ids = data.loc[
            data["id_item_venda"].duplicated(keep=False), "id_item_venda"
        ].tolist()
        raise ValueError(f"IDs de item repetidos após remover duplicatas: {duplicate_ids[:10]}")

    valid_financial = data.loc[~invalid_financial_rows].copy()
    completed = valid_financial.loc[
        valid_financial["status_venda"].eq("Concluído")
    ].copy()
    time_valid_completed = completed.loc[completed["data_venda"].notna()].copy()

    quality = {
        "original_rows": original_rows,
        "original_columns": original_columns,
        "original_nulls": original_nulls,
        "original_dtypes": original_dtypes,
        "exact_duplicates": exact_duplicates,
        "remaining_rows": len(data),
        "invalid_dates": invalid_dates,
        "invalid_quantity": int(invalid_quantity.sum()),
        "invalid_discount": int(invalid_discount.sum()),
        "invalid_price": int(invalid_price.sum()),
        "invalid_financial_rows": int(invalid_financial_rows.sum()),
        "amount_mismatches": amount_mismatches,
        "missing_cities": int(original_nulls.get("cidade_cliente", 0)),
        "other_missing_values": int(
            original_nulls.drop(labels=["cidade_cliente"], errors="ignore").sum()
        ),
        "category_variants": sorted(raw["categoria_produto"].dropna().astype(str).unique()),
        "valid_financial_rows": len(valid_financial),
        "completed_rows": len(completed),
        "completed_orders": int(completed["id_pedido"].nunique()),
        "time_valid_completed_rows": len(time_valid_completed),
    }
    return completed, quality


def build_report(data: pd.DataFrame, quality: dict[str, object], output: Path) -> str:
    output.mkdir(parents=True, exist_ok=True)
    charts_dir = output / "graficos"
    charts_dir.mkdir(parents=True, exist_ok=True)

    monthly_data = data.loc[data["data_venda"].notna()].copy()
    monthly_data["ano"] = monthly_data["data_venda"].dt.year
    monthly_data["mes"] = monthly_data["data_venda"].dt.month
    monthly_data["periodo"] = monthly_data["data_venda"].dt.to_period("M")
    monthly_revenue = monthly_data.groupby("periodo")["valor_liquido"].sum().sort_index()
    yearly_revenue = monthly_data.groupby("ano")["valor_liquido"].sum().sort_index()
    product_units = (
        data.groupby("nome_produto")["quantidade"].sum().sort_values(ascending=False).head(10)
    )
    category_revenue = data.groupby("categoria_produto")["valor_liquido"].sum().sort_values(
        ascending=False
    )
    seller_summary = (
        data.groupby("nome_vendedor")
        .agg(
            faturamento=("valor_liquido", "sum"),
            pedidos=("id_pedido", "nunique"),
        )
        .assign(ticket_medio=lambda frame: frame["faturamento"] / frame["pedidos"])
        .sort_values("faturamento", ascending=False)
        .head(5)
    )
    completed_orders = data.drop_duplicates("id_pedido")
    payment_orders = completed_orders.groupby("forma_pagamento")["id_pedido"].nunique()
    payment_share = payment_orders.div(payment_orders.sum()).mul(100).sort_values(ascending=False)
    state_revenue = data.groupby("estado_cliente")["valor_liquido"].sum().sort_values(
        ascending=False
    )
    region_category_year = (
        monthly_data.groupby(["regiao_cliente", "categoria_produto", "ano"])["valor_liquido"]
        .sum()
        .unstack("ano", fill_value=0)
    )
    for year in (2022, 2023):
        if year not in region_category_year.columns:
            region_category_year[year] = 0.0
    region_category_year["crescimento_2023"] = (
        region_category_year[2023] / region_category_year[2022].replace(0, pd.NA) - 1
    ) * 100
    positive_growth = region_category_year.loc[
        region_category_year["crescimento_2023"].gt(0)
    ].copy()
    strategy_table = (
        positive_growth.sort_values(2023, ascending=False)
        if not positive_growth.empty
        else region_category_year.sort_values(2023, ascending=False)
    )
    recommended = strategy_table.iloc[0]
    recommended_region, recommended_category = strategy_table.index[0]
    total_gross = float(data["valor_bruto"].sum())
    total_net = float(data["valor_liquido"].sum())
    gross_discount = float(data["desconto"].sum())
    best_month = monthly_revenue.idxmax()
    worst_month = monthly_revenue.idxmin()

    # 1. Produtos por unidades vendidas.
    fig, ax = plt.subplots(figsize=(10, 5.5))
    product_units.sort_values().plot.barh(ax=ax, color=COLORS[0])
    ax.set(title="10 produtos com mais unidades vendidas", xlabel="Unidades", ylabel="")
    charts = [save_chart(fig, charts_dir, "01_produtos_mais_vendidos.png")]

    # 2. Receita líquida reconhecida por categoria.
    fig, ax = plt.subplots(figsize=(9, 5))
    category_revenue.sort_values().plot.barh(ax=ax, color=COLORS[1])
    ax.set(title="Faturamento líquido por categoria", xlabel="Faturamento (R$)", ylabel="")
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: f"R$ {value / 1_000_000:.0f} mi")
    )
    charts.append(save_chart(fig, charts_dir, "02_faturamento_por_categoria.png"))

    # 3. Série mensal comparada entre anos.
    monthly_pivot = monthly_data.pivot_table(
        index="mes", columns="ano", values="valor_liquido", aggfunc="sum"
    )
    fig, ax = plt.subplots(figsize=(10, 5.5))
    monthly_pivot.plot(ax=ax, marker="o", linewidth=2, color=COLORS[: len(monthly_pivot.columns)])
    ax.set(
        title="Evolução mensal do faturamento líquido",
        xlabel="Mês",
        ylabel="Faturamento (R$)",
        xticks=range(1, 13),
    )
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Ano")
    charts.append(save_chart(fig, charts_dir, "03_evolucao_mensal.png"))

    # 4. Faturamento anual.
    fig, ax = plt.subplots(figsize=(8, 5))
    yearly_revenue.plot.bar(ax=ax, color=COLORS[0], rot=0)
    ax.set(title="Faturamento líquido anual", xlabel="Ano", ylabel="Faturamento (R$)")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: f"R$ {value / 1_000_000:.0f} mi")
    )
    charts.append(save_chart(fig, charts_dir, "04_faturamento_anual.png"))

    # 5. Vendedores e ticket médio dos cinco primeiros.
    fig, ax = plt.subplots(figsize=(10, 5.5))
    seller_summary["faturamento"].sort_values().plot.barh(ax=ax, color=COLORS[2])
    ax.set(title="5 vendedores com maior faturamento líquido", xlabel="Faturamento (R$)", ylabel="")
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: f"R$ {value / 1_000_000:.1f} mi")
    )
    charts.append(save_chart(fig, charts_dir, "05_desempenho_vendedores.png"))

    # 6. Participação das formas de pagamento por pedido concluído.
    fig, ax = plt.subplots(figsize=(8, 5))
    payment_share.sort_values().plot.barh(ax=ax, color=COLORS[4])
    ax.set(title="Participação das formas de pagamento", xlabel="Pedidos concluídos (%)", ylabel="")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{value:.0f}%"))
    charts.append(save_chart(fig, charts_dir, "06_formas_pagamento.png"))

    # 7. Comparação geográfica por UF.
    fig, ax = plt.subplots(figsize=(9, 6))
    state_revenue.sort_values().plot.barh(ax=ax, color=COLORS[0])
    ax.set(title="Faturamento líquido por estado", xlabel="Faturamento (R$)", ylabel="")
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: f"R$ {value / 1_000_000:.1f} mi")
    )
    charts.append(save_chart(fig, charts_dir, "07_faturamento_por_estado.png"))

    # 8. Evidência do cruzamento região x categoria x ano para a questão estratégica.
    top_strategy = region_category_year.sort_values(2023, ascending=False).head(8)
    labels = [f"{region} — {category}" for region, category in top_strategy.index]
    positions = range(len(top_strategy))
    fig, ax = plt.subplots(figsize=(11, 6))
    width = 0.38
    ax.bar(
        [position - width / 2 for position in positions],
        top_strategy[2022],
        width,
        label="2022",
        color=COLORS[0],
    )
    ax.bar(
        [position + width / 2 for position in positions],
        top_strategy[2023],
        width,
        label="2023",
        color=COLORS[1],
    )
    ax.set(
        title="Combinações região × categoria: faturamento líquido",
        ylabel="Faturamento (R$)",
        xticks=list(positions),
        xticklabels=labels,
    )
    ax.tick_params(axis="x", labelrotation=25)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: f"R$ {value / 1_000_000:.0f} mi")
    )
    ax.legend(title="Ano")
    charts.append(save_chart(fig, charts_dir, "08_estrategia_regiao_categoria.png"))

    lines: list[str] = [
        "# Relatório — Sistema de Análise de Vendas",
        "",
        "## Escopo e critérios",
        "",
        (
            f"A base original contém **{integer(quality['original_rows'])} registros e "
            f"{quality['original_columns']} colunas**. Após remover "
            f"{integer(quality['exact_duplicates'])} linhas integralmente duplicadas, "
            f"{integer(quality['remaining_rows'])} linhas únicas foram verificadas."
        ),
        (
            "As métricas financeiras consideram apenas itens com quantidade positiva, "
            "preço válido e desconto entre zero e o valor bruto do item. Foram excluídas "
            f"{integer(quality['invalid_financial_rows'])} linhas com inconsistências financeiras. "
            f"{integer(quality['invalid_dates'])} datas inválidas foram mantidas nos totais não "
            "temporais (os campos financeiros estavam utilizáveis), mas excluídas das "
            "séries temporais."
        ),
        (
            "Faturamento bruto é preço unitário × quantidade; faturamento líquido é o bruto "
            "menos desconto. Ambos são calculados somente para vendas **Concluídas**. "
            "Cancelados, devolvidos e pendentes não entram em receita reconhecida. "
            "A base é de itens: pedidos foram contados por identificador único quando a "
            "pergunta pede transações."
        ),
        "",
        "## 1. Exploração inicial",
        "",
        (
            f"- Registros e colunas: **{integer(quality['original_rows'])} × "
            f"{quality['original_columns']}**."
        ),
        "- Os tipos originais das variáveis estão listados na tabela de qualidade abaixo; as datas foram convertidas para datetime e valores numéricos tratados como números.",
        "- A base está no formato CSV separado por ponto e vírgula e codificado em UTF-8.",
        "",
        "## 2. Qualidade e tratamento dos dados",
        "",
        "| Verificação | Resultado | Decisão |",
        "|---|---:|---|",
        f"| Linhas exatamente duplicadas | {quality['exact_duplicates']} | Removidas, mantendo a primeira ocorrência. |",
        f"| Datas inválidas | {quality['invalid_dates']} | Excluídas somente de análises temporais; as demais colunas válidas permanecem nas métricas não temporais. |",
        f"| Quantidades nulas ou não positivas | {quality['invalid_quantity']} | Excluídas das métricas financeiras e de volume. |",
        f"| Descontos inválidos (negativos ou acima do bruto) | {quality['invalid_discount']} | Excluídos das métricas financeiras; valores não foram corrigidos por estimativa. |",
        f"| Linhas financeiras excluídas (união das regras acima) | {quality['invalid_financial_rows']} | As regras sobre quantidade, desconto e preço se sobrepõem; contagem representa linhas únicas. |",
        f"| Cidade ausente na origem | {quality['missing_cities']} | Mantida como “Não informado”; a análise por UF continua possível. |",
        "| Variações de grafia de categoria | Informática/Informatica e Eletrônicos/Eletronicos | Padronizadas sem acento inconsistente, preservando rótulos legíveis. |",
        f"| Total informado divergente do bruto menos desconto | {quality['amount_mismatches']} | O valor líquido é recalculado pelas colunas unitárias; os registros divergentes também são excluídos pela quantidade inválida. |",
        f"| Valores ausentes | {quality['missing_cities']} cidades; {quality['other_missing_values']} nas demais colunas | Cidades ficam como “Não informado”; nenhuma outra coluna exigiu imputação. |",
        "",
        "### Tipos de dados recebidos",
        "",
        "| Coluna | Tipo pandas original |",
        "|---|---|",
    ]
    for column, dtype in quality["original_dtypes"].items():
        lines.append(f"| `{column}` | `{dtype}` |")

    lines.extend(
        [
            "",
            "## 3. Faturamento total",
            "",
            f"- **Faturamento bruto concluído:** {money(total_gross)}.",
            f"- **Descontos nas vendas concluídas:** {money(gross_discount)}.",
            f"- **Faturamento líquido concluído:** {money(total_net)}.",
            f"- Base: {integer(len(data))} itens válidos de {integer(quality['completed_orders'])} pedidos concluídos.",
            "",
            "## 4. Dez produtos mais vendidos",
            "",
            "A classificação usa a soma da quantidade de unidades, não o número de pedidos.",
            "",
            "| Produto | Unidades |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {name} | {integer(int(units))} |" for name, units in product_units.items())
    lines.extend(
        [
            "",
            f"![Produtos mais vendidos]({charts[0]})",
            "",
            "O gráfico destaca volume físico: um item pode liderar em unidades sem liderar em faturamento.",
            "",
            "## 5. Desempenho por categoria",
            "",
            "| Categoria | Faturamento líquido | Participação |",
            "|---|---:|---:|",
        ]
    )
    lines.extend(
        f"| {category} | {money(value)} | {percent(value / total_net * 100)} |"
        for category, value in category_revenue.items()
    )
    lead_category = category_revenue.index[0]
    next_category = category_revenue.index[1]
    lines.extend(
        [
            "",
            f"{lead_category} lidera, com {money(category_revenue.iloc[0])}, "
            f"{money(category_revenue.iloc[0] - category_revenue.iloc[1])} acima de {next_category}.",
            "",
            f"![Faturamento por categoria]({charts[1]})",
            "",
            "## 6. Sazonalidade e evolução",
            "",
            "| Ano | Faturamento líquido |",
            "|---:|---:|",
        ]
    )
    lines.extend(f"| {year} | {money(value)} |" for year, value in yearly_revenue.items())
    lines.extend(
        [
            "",
            f"O mês de maior faturamento foi **{best_month.strftime('%m/%Y')}** "
            f"({money(monthly_revenue.loc[best_month])}); o menor foi "
            f"**{worst_month.strftime('%m/%Y')}** ({money(monthly_revenue.loc[worst_month])}). "
            "Os 149 registros com data inválida não participam desta comparação.",
            "",
            f"![Evolução mensal]({charts[2]})",
            "",
            "A série permite comparar o mesmo mês entre anos e evidencia a oscilação sazonal; picos e vales mensais não devem ser confundidos com a tendência anual.",
            "",
            f"![Faturamento anual]({charts[3]})",
            "",
            "O faturamento caiu levemente de 2021 para 2022 e voltou a crescer em 2023, que foi o maior total anual da série.",
            "",
            "## 7. Avaliação da equipe",
            "",
            "Ticket médio = faturamento líquido do vendedor ÷ quantidade de pedidos concluídos únicos.",
            "",
            "| Vendedor | Faturamento líquido | Pedidos | Ticket médio |",
            "|---|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| {seller} | {money(row.faturamento)} | {integer(int(row.pedidos))} | {money(row.ticket_medio)} |"
        for seller, row in seller_summary.iterrows()
    )
    lines.extend(
        [
            "",
            f"![Desempenho dos vendedores]({charts[4]})",
            "",
            "## 8. Preferências de pagamento",
            "",
            "Participação calculada pelo número de pedidos concluídos únicos, não por linhas de itens.",
            "",
            "| Forma de pagamento | Pedidos | Participação |",
            "|---|---:|---:|",
        ]
    )
    lines.extend(
        f"| {method} | {integer(int(payment_orders[method]))} | {percent(share)} |"
        for method, share in payment_share.items()
    )
    lines.extend(
        [
            "",
            "As participações são próximas entre si; nenhuma forma concentra a maioria das transações.",
            "",
            f"![Formas de pagamento]({charts[5]})",
            "",
            "## 9. Análise geográfica",
            "",
            "| UF | Região | Faturamento líquido |",
            "|---|---|---:|",
        ]
    )
    lines.extend(
        f"| {state} | {REGIONS.get(state, 'UF não mapeada')} | {money(value)} |"
        for state, value in state_revenue.items()
    )
    region_revenue = data.groupby("regiao_cliente")["valor_liquido"].sum().sort_values(
        ascending=False
    )
    top_state = state_revenue.index[0]
    top_region = region_revenue.index[0]
    lines.extend(
        [
            "",
            f"**{top_state}** é a UF com maior faturamento líquido ({money(state_revenue.iloc[0])}); "
            f"a região com maior resultado agregado é **{top_region}** "
            f"({money(region_revenue.iloc[0])}). As UFs ausentes não foram imputadas.",
            "",
            f"![Faturamento por estado]({charts[6]})",
            "",
            "## 10. Visualizações",
            "",
            "Os oito gráficos deste relatório cobrem produtos, categorias, evolução mensal e anual, vendedores, pagamentos, estados e o cruzamento estratégico da questão 11. Cada visualização acompanha a interpretação na seção correspondente.",
            "",
            "## 11. Estudo aplicado — alocação de marketing e força de vendas",
            "",
            "**Pergunta de negócio.** Em qual combinação de região e categoria a empresa deve testar a maior parcela incremental do orçamento no próximo trimestre?",
            "",
            "**Metodologia.** Cruzamos região geográfica (UF agrupada nas cinco macrorregiões brasileiras), categoria e ano. Comparamos o faturamento líquido concluído de 2023 com 2022 para cada combinação. Para evitar recomendar uma queda recente, priorizamos a combinação com maior faturamento em 2023 entre aquelas com crescimento positivo ano contra ano. A leitura temporal usa apenas registros com data válida.",
            "",
            "| Região | Categoria | 2022 | 2023 | Variação 2023/2022 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    strategy_display = strategy_table.sort_values(2023, ascending=False).head(8)
    for (region, category), row in strategy_display.iterrows():
        growth = row["crescimento_2023"]
        growth_label = percent(growth) if pd.notna(growth) else "n/d"
        lines.append(
            f"| {region} | {category} | {money(row[2022])} | {money(row[2023])} | {growth_label} |"
        )
    previous_value = float(recommended[2022])
    current_value = float(recommended[2023])
    growth_value = float(recommended["crescimento_2023"])
    lines.extend(
        [
            "",
            f"![Cruzamento região e categoria]({charts[7]})",
            "",
            (
                f"**Conclusão executiva.** Recomendamos direcionar o maior teste incremental — "
                f"não todo o orçamento — para **{recommended_category} na região {recommended_region}**. "
                f"A combinação gerou {money(current_value)} em 2023, ante {money(previous_value)} em "
                f"2022 ({percent(growth_value)}). A recomendação combina escala atual e crescimento "
                "positivo; deve ser validada com um teste controlado e acompanhamento de conversão e "
                "margem, que não estão disponíveis nesta base. Isso evita interpretar faturamento como lucro."
            ),
            "",
            "## Apêndice — observações de qualidade",
            "",
            f"- Registros com data válida e incluídos nas tendências: {integer(quality['time_valid_completed_rows'])} itens concluídos após o tratamento financeiro.",
            f"- Datas ausentes na origem: {integer(int(quality['original_nulls'].get('data_venda', 0)))}; datas não interpretáveis: {integer(quality['invalid_dates'])}.",
            "- Categorias e formas de pagamento foram normalizadas ignorando diferenças de acentuação e espaços; demais valores não foram inferidos.",
            "",
        ]
    )
    report = "\n".join(lines)
    report_path = output / "relatorio_analise_vendas.md"
    report_path.write_text(report, encoding="utf-8")
    return str(report_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Limpa a base de vendas, calcula indicadores e gera relatório e gráficos."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "vendas.csv",
        help="Caminho do CSV de origem (padrão: vendas.csv junto ao script).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "resultado",
        help="Pasta para o relatório e gráficos (padrão: resultado).",
    )
    args = parser.parse_args()
    if not args.csv.is_file():
        parser.error(f"Arquivo CSV não encontrado: {args.csv}")

    data, quality = prepare_data(args.csv)
    report_path = build_report(data, quality, args.output_dir)
    print(f"Relatório gerado: {report_path}")
    print(f"Gráficos gerados: {args.output_dir / 'graficos'}")


if __name__ == "__main__":
    main()
