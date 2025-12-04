"""Painel de chat NLQ (Natural Language Query)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.services.chat_service import answer_question


def render_chat_panel(cost_df: pd.DataFrame) -> None:
    """Renderiza painel de chat com IA."""
    st.markdown("### Chat com IA")
    st.caption("Faça perguntas em linguagem natural sobre seus custos")

    if cost_df.empty:
        st.info("Sem dados disponíveis. Importe um CSV para começar a fazer perguntas.")
        # Input sempre visível, mesmo sem dados
        user_query = st.chat_input("Digite sua pergunta aqui... (importe um CSV primeiro)")
        if user_query:
            st.warning("Por favor, importe um CSV primeiro para fazer perguntas.")
        return

    # Histórico de conversa
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Exibir histórico
    if st.session_state.chat_history:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if "dataframe" in msg and msg["dataframe"]:
                    st.dataframe(pd.DataFrame(msg["dataframe"]), use_container_width=True)
    else:
        # Mensagem inicial se não houver histórico
        with st.chat_message("assistant"):
            st.markdown("Olá! Faça perguntas sobre seus custos em linguagem natural. Exemplos:")
            st.markdown("- Qual serviço mais consumido nos últimos meses?")
            st.markdown("- Qual foi o custo total em outubro?")
            st.markdown("- Quais são os 5 serviços mais caros?")

    # Input do usuário
    # st.chat_input aparece fixo na parte inferior da tela
    # Se não aparecer, pode ser problema de versão do Streamlit ou CSS
    try:
        user_query = st.chat_input("Digite sua pergunta aqui...")
    except AttributeError:
        # Fallback para versões antigas do Streamlit
        st.markdown("---")
        col1, col2 = st.columns([6, 1])
        with col1:
            user_query = st.text_input("Digite sua pergunta:", key="chat_input", placeholder="Ex: Qual serviço mais consumido nos últimos meses?")
        with col2:
            submit = st.button("Enviar", type="primary")
        if not submit:
            user_query = None

    if user_query:
        # Adicionar pergunta ao histórico
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        # Gerar resposta
        with st.spinner("Pensando..."):
            response = answer_question(user_query, cost_df)

        # Adicionar resposta ao histórico
        response_dict = {"role": "assistant", "content": response.answer_text}
        if response.dataframe:
            response_dict["dataframe"] = response.dataframe
        st.session_state.chat_history.append(response_dict)

        # Recarregar para exibir nova mensagem
        st.rerun()


