"""Ferramentas de cálculo — consumo elétrico e fotovoltaico preliminar (#38)."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from geoai.tools import (
    ApplianceUse,
    appliance_monthly_kwh,
    monthly_cost_brl,
    pv_preliminary_sizing,
)

from _bootstrap import configure_page, render_footer, sidebar_brand

configure_page("Ferramentas de cálculo", icon="🧮")
sidebar_brand()


def _br(value: float, digits: int = 2) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


st.title("Ferramentas de cálculo")
st.caption(
    "Cálculos determinísticos com as **suas** entradas. Nenhum parâmetro é "
    "estimado por inteligência artificial. O resultado é uma simulação "
    "preliminar, não um projeto nem um estudo de viabilidade."
)

tab_consumo, tab_fv = st.tabs(
    ["Consumo e custo de equipamentos", "Dimensionamento fotovoltaico preliminar"]
)

with tab_consumo:
    st.subheader("Quanto meus equipamentos consomem?")
    st.caption(
        "Preencha a tabela com a potência de placa de cada equipamento e o "
        "tempo de uso. As linhas iniciais são apenas um modelo de "
        "preenchimento: substitua pelos seus valores."
    )
    template = pd.DataFrame(
        [
            {
                "Equipamento": "Exemplo: motor",
                "Potência (W)": 1500.0,
                "Horas por dia": 4.0,
                "Dias por mês": 22.0,
                "Quantidade": 1.0,
            },
            {
                "Equipamento": "Exemplo: iluminação",
                "Potência (W)": 40.0,
                "Horas por dia": 8.0,
                "Dias por mês": 30.0,
                "Quantidade": 10.0,
            },
        ]
    )
    edited = st.data_editor(
        template,
        num_rows="dynamic",
        width="stretch",
        key="tool_appliances",
        column_config={
            "Potência (W)": st.column_config.NumberColumn(min_value=0.0),
            "Horas por dia": st.column_config.NumberColumn(
                min_value=0.0, max_value=24.0
            ),
            "Dias por mês": st.column_config.NumberColumn(
                min_value=0.0, max_value=31.0
            ),
            "Quantidade": st.column_config.NumberColumn(min_value=0.0),
        },
    )
    tariff = st.number_input(
        "Tarifa com tributos (R$/kWh), conforme a sua fatura",
        min_value=0.0,
        value=None,
        step=0.01,
        format="%.4f",
        placeholder="Ex.: valor total da fatura ÷ kWh consumidos",
        help=(
            "A plataforma não assume tarifa. Informe o valor da sua fatura "
            "ou consulte a distribuidora."
        ),
    )

    rows: list[dict[str, object]] = []
    skipped = 0
    for rec in edited.to_dict("records"):
        values = [
            rec.get("Potência (W)"),
            rec.get("Horas por dia"),
            rec.get("Dias por mês"),
            rec.get("Quantidade"),
        ]
        if any(v is None or pd.isna(v) for v in values):
            skipped += 1
            continue
        try:
            kwh = appliance_monthly_kwh(
                ApplianceUse(
                    name=str(rec.get("Equipamento") or ""),
                    power_w=values[0],
                    hours_per_day=values[1],
                    days_per_month=values[2],
                    quantity=values[3],
                )
            )
        except ValueError:
            skipped += 1
            continue
        rows.append(
            {"Equipamento": rec.get("Equipamento") or "(sem nome)", "kWh/mês": kwh}
        )

    total_kwh = sum(float(r["kWh/mês"]) for r in rows)
    st.session_state["tool_total_kwh"] = total_kwh
    c1, c2 = st.columns(2)
    c1.metric("Consumo estimado (kWh/mês)", _br(total_kwh, 1))
    if tariff is None:
        c2.metric("Custo estimado (R$/mês)", "informe a tarifa")
    else:
        c2.metric(
            "Custo estimado (R$/mês)",
            _br(monthly_cost_brl(total_kwh, tariff)),
        )
    if skipped:
        st.warning(
            f"{skipped} linha(s) incompleta(s) ou inválida(s) ficaram fora "
            "do cálculo. Linha sem valor não é tratada como zero."
        )
    if rows:
        out = pd.DataFrame(rows).sort_values("kWh/mês", ascending=False)
        st.bar_chart(out, x="Equipamento", y="kWh/mês", horizontal=True)
        st.download_button(
            "Baixar resultado (CSV)",
            out.to_csv(index=False).encode("utf-8"),
            file_name="napi_geoai_consumo.csv",
            mime="text/csv",
        )
    with st.expander("Fórmula e limitações"):
        st.latex(
            r"E_{\text{mês}}[\mathrm{kWh}] = "
            r"\frac{P[\mathrm{W}] \times h \times d \times n}{1000}"
            r"\qquad C[\mathrm{R\$}] = E \times \text{tarifa}"
        )
        st.markdown(
            "- A potência de placa é o valor nominal: o consumo real depende "
            "do regime de carga do equipamento.\n"
            "- Não inclui demanda contratada, bandeiras tarifárias, "
            "iluminação pública nem tarifas horárias.\n"
            "- Classe do resultado: **C, simulação** com entradas do usuário."
        )

with tab_fv:
    st.subheader("Que potência fotovoltaica compensaria meu consumo?")
    st.caption(
        "Estimativa de ordem de grandeza. A irradiação do seu local **não** "
        "é preenchida pela plataforma nesta versão: informe o valor "
        "consultado em uma fonte técnica."
    )
    suggested = float(st.session_state.get("tool_total_kwh") or 0.0)
    f1, f2 = st.columns(2)
    with f1:
        monthly = st.number_input(
            "Consumo mensal a compensar (kWh/mês)",
            min_value=0.0,
            value=suggested if suggested > 0 else None,
            step=10.0,
            placeholder="Média das últimas 12 faturas",
        )
        hsp = st.number_input(
            "Irradiação no plano dos módulos, HSP (kWh/m²/dia)",
            min_value=0.0,
            value=None,
            step=0.1,
            placeholder="Consulte INPE/LABREN ou CRESESB SunData",
            help=(
                "Média diária anual para o seu município. Fontes: Atlas "
                "Brasileiro de Energia Solar (INPE/LABREN) e SunData "
                "(CRESESB/CEPEL)."
            ),
        )
    with f2:
        pr = st.slider(
            "Taxa de desempenho do sistema (PR) — hipótese",
            min_value=0.60,
            max_value=0.90,
            value=0.75,
            step=0.01,
            help=(
                "Hipótese de simulação que agrega perdas por temperatura, "
                "inversor, cabeamento e sujeira. Ajuste conforme o projeto."
            ),
        )
        module_wp = st.number_input(
            "Potência de um módulo (Wp) — hipótese",
            min_value=1.0,
            value=550.0,
            step=5.0,
            help="Use o valor da folha de dados do módulo pretendido.",
        )

    if monthly is None or hsp is None:
        st.info(
            "Informe o consumo mensal e a irradiação (HSP) para calcular. "
            "Sem esses dois valores não há resultado."
        )
    else:
        try:
            res = pv_preliminary_sizing(monthly, hsp, pr, module_wp=module_wp)
        except ValueError as exc:
            st.error(f"Entrada inválida: {exc}.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Potência necessária (kWp)", _br(res.power_kwp))
            m2.metric("Módulos (arredondado para cima)", str(res.module_count))
            m3.metric(
                "Geração média esperada (kWh/mês)",
                _br(res.expected_monthly_kwh or 0.0, 0),
                help="Com a quantidade inteira de módulos e as hipóteses acima.",
            )
            lo = pv_preliminary_sizing(monthly, hsp, min(pr + 0.05, 1.0))
            hi = pv_preliminary_sizing(monthly, hsp, max(pr - 0.05, 0.01))
            st.caption(
                f"Sensibilidade ao PR (±0,05): de **{_br(lo.power_kwp)}** a "
                f"**{_br(hi.power_kwp)} kWp**."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        ("Consumo mensal (kWh)", _br(monthly, 1), "entrada do usuário"),
                        ("HSP (kWh/m²/dia)", _br(hsp), "entrada do usuário"),
                        ("PR", _br(pr), "hipótese de simulação"),
                        ("Módulo (Wp)", _br(module_wp, 0), "hipótese de simulação"),
                        ("Dias no mês", "30", "convenção de cálculo"),
                    ],
                    columns=["Parâmetro", "Valor", "Origem"],
                ),
                hide_index=True,
                width="stretch",
            )
    with st.expander("Fórmula e limitações"):
        st.latex(
            r"P[\mathrm{kWp}] = \frac{E_{\text{mês}}}"
            r"{HSP \times 30 \times PR}"
        )
        st.markdown(
            "- Não considera custo de disponibilidade, sombreamento, "
            "orientação, inclinação real, degradação nem sazonalidade.\n"
            "- Não avalia conexão à rede, parecer de acesso, licenciamento, "
            "preço de equipamentos nem retorno financeiro.\n"
            "- Potência (kWp) não é energia (kWh): a geração varia mês a mês.\n"
            "- Classe do resultado: **C, simulação**. Um projeto exige "
            "responsável técnico habilitado."
        )

render_footer()
