"""Serviço de chat NLQ (Natural Language Query) sobre custos."""
from __future__ import annotations

import ast
import re
from typing import Dict, Optional

import pandas as pd

from app.data.models import ChatResponse
from app.infra.llm_client import LLMClient
from app.models.cost_model import DATE_COLUMN, TOTAL_COLUMN


def answer_question(user_query: str, cost_df: pd.DataFrame) -> ChatResponse:
    """
    Responde perguntas em linguagem natural sobre os dados de custos.

    Args:
        user_query: Pergunta do usuário em português
        cost_df: DataFrame de custos

    Returns:
        ChatResponse com resposta, DataFrame opcional e especificação de gráfico
    """
    if cost_df.empty:
        return ChatResponse(
            answer_text="⚠️ Não há dados disponíveis para responder sua pergunta. Por favor, importe um CSV primeiro."
        )

    # Tentar análise direta primeiro (mais precisa)
    direct_result = _try_direct_analysis(user_query, cost_df)
    if direct_result:
        return direct_result

    # Preparar contexto sobre os dados
    context = _build_data_context(cost_df)

    # Gerar resposta usando LLM
    system_prompt = f"""Você é um assistente especializado em análise de custos FinOps.
Quando o usuário fizer perguntas sobre custos, você deve:
1. Analisar a pergunta cuidadosamente
2. Gerar código Pandas CORRETO e SIMPLES para responder
3. Explicar o resultado em português de forma clara

ESTRUTURA DOS DADOS:
- A coluna "{DATE_COLUMN}" contém as datas (período de uso)
- Os serviços são as outras colunas (ex: nomes de serviços AWS ou OCI)
- Cada linha representa um período (geralmente um mês)
- Os valores nas colunas de serviços são os custos em dólares
- A coluna "{TOTAL_COLUMN}" contém o total daquele período (soma dos serviços)

IMPORTANTE: 
- Use apenas operações seguras do Pandas
- O código deve ser SIMPLES e DIRETO
- Retorne o código em um bloco marcado com ```python
- O código deve atribuir o resultado final à variável 'result'
- Seja objetivo e claro na explicação"""

    user_prompt = f"""Dados disponíveis:
{context}

Pergunta do usuário: {user_query}

Gere:
1. Uma explicação clara em português da resposta
2. Código Pandas SIMPLES e CORRETO para calcular a resposta (entre ```python e ```)
   - O código deve usar 'df' como o DataFrame
   - O resultado final deve ser atribuído à variável 'result'
   - Se for um valor único, use: result = pd.DataFrame([{{'resposta': valor}}])
   - Se for uma lista/ranking, use: result = pd.DataFrame(...)
3. Se aplicável, sugestão de visualização"""

    llm_client = LLMClient()
    response = llm_client.generate(system_prompt, user_prompt, temperature=0.2)

    # Extrair código Python se houver
    code_match = re.search(r"```python\n(.*?)\n```", response, re.DOTALL)
    if code_match:
        code = code_match.group(1).strip()
        try:
            # Executar código de forma segura
            result_df = _execute_safe_code(code, cost_df)
            if result_df is not None and not result_df.empty:
                # Formatar resposta com o resultado
                answer_text = _format_answer_with_result(response, result_df)
                return ChatResponse(
                    answer_text=answer_text,
                    dataframe=result_df.head(20).to_dict("records"),  # Limitar a 20 linhas
                )
        except Exception as e:
            return ChatResponse(
                answer_text=f"{response}\n\n⚠️ Erro ao executar análise: {str(e)}\n\nTente reformular sua pergunta de forma mais específica."
            )

    return ChatResponse(answer_text=response)


def _try_direct_analysis(user_query: str, cost_df: pd.DataFrame) -> Optional[ChatResponse]:
    """Tenta análise direta para perguntas comuns (mais precisa)."""
    query_lower = user_query.lower()

    # Pergunta sobre serviço mais consumido/mais caro (últimos meses, geral, etc)
    if any(word in query_lower for word in ["mais consumido", "mais caro", "maior custo", "maior gasto", "maior valor", "mais usado", "mais utilizado"]):
        return _analyze_most_expensive_service(user_query, cost_df)

    # Pergunta sobre serviço mais usado/frequente
    if any(word in query_lower for word in ["maior frequencia", "mais frequente"]):
        return _analyze_most_frequent_service(user_query, cost_df)

    # Pergunta sobre total/custo total
    if any(word in query_lower for word in ["total", "soma", "gasto total", "custo total"]):
        return _analyze_total_cost(user_query, cost_df)

    # Pergunta sobre período específico
    if any(word in query_lower for word in ["outubro", "novembro", "dezembro", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro"]):
        return _analyze_period(user_query, cost_df)

    return None


def _analyze_most_frequent_service(user_query: str, cost_df: pd.DataFrame) -> ChatResponse:
    """Analisa qual serviço foi mais usado (maior número de registros com custo > 0)."""
    # Filtrar por período se mencionado
    filtered_df = _filter_by_period(user_query, cost_df)

    # Contar quantas vezes cada serviço teve custo > 0
    service_cols = [col for col in filtered_df.columns if col not in [DATE_COLUMN, TOTAL_COLUMN]]
    frequency = {}
    for col in service_cols:
        count = (filtered_df[col] > 0).sum()
        if count > 0:
            frequency[col] = count

    if not frequency:
        return ChatResponse(answer_text="⚠️ Não foi possível identificar serviços com custos no período especificado.")

    # Ordenar por frequência
    sorted_freq = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
    top_service, top_count = sorted_freq[0]

    # Criar DataFrame com resultado
    result_df = pd.DataFrame([
        {"Serviço": service, "Frequência": count}
        for service, count in sorted_freq[:10]
    ])

    answer = f"**Serviço com maior frequência:** {top_service.replace('($)', '')}\n\n"
    answer += f"Este serviço teve custos registrados em **{top_count}** período(s) dos {len(filtered_df)} analisados.\n\n"
    answer += "**Top 10 serviços por frequência:**"

    return ChatResponse(
        answer_text=answer,
        dataframe=result_df.to_dict("records")
    )


def _analyze_most_expensive_service(user_query: str, cost_df: pd.DataFrame) -> ChatResponse:
    """Analisa qual serviço teve maior custo total."""
    query_lower = user_query.lower()
    
    # Filtrar por período se mencionado
    filtered_df = cost_df.copy()
    
    # Verificar se menciona "últimos meses" ou similar
    if any(word in query_lower for word in ["ultimos", "últimos", "recentes", "recente"]):
        # Pegar últimos N meses (padrão: 3)
        import re
        months_match = re.search(r"(\d+)\s*(meses|mês)", query_lower)
        n_months = int(months_match.group(1)) if months_match else 3
        
        if DATE_COLUMN in filtered_df.columns:
            try:
                filtered_df[DATE_COLUMN] = pd.to_datetime(filtered_df[DATE_COLUMN], errors="coerce")
                filtered_df = filtered_df.dropna(subset=[DATE_COLUMN])
                if not filtered_df.empty:
                    # Ordenar por data e pegar últimos N meses
                    filtered_df = filtered_df.sort_values(DATE_COLUMN)
                    last_date = filtered_df[DATE_COLUMN].max()
                    cutoff_date = last_date - pd.DateOffset(months=n_months)
                    filtered_df = filtered_df[filtered_df[DATE_COLUMN] >= cutoff_date]
            except Exception:
                pass
    else:
        # Filtrar por período específico se mencionado
        filtered_df = _filter_by_period(user_query, cost_df)

    # Calcular totais por serviço
    service_cols = [col for col in filtered_df.columns if col not in [DATE_COLUMN, TOTAL_COLUMN]]
    totals = {}
    for col in service_cols:
        total = float(filtered_df[col].sum())
        if total > 0:
            totals[col] = total

    if not totals:
        return ChatResponse(answer_text="⚠️ Não foi possível identificar serviços com custos no período especificado.")

    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    top_service, top_cost = sorted_totals[0]

    result_df = pd.DataFrame([
        {"Serviço": service.replace("($)", ""), "Custo Total": f"${cost:,.2f}"}
        for service, cost in sorted_totals[:10]
    ])

    period_info = ""
    if any(word in query_lower for word in ["ultimos", "últimos", "recentes"]):
        period_info = f" nos últimos {n_months} meses"
    
    answer = f"**Serviço mais consumido{period_info}:** {top_service.replace('($)', '')}\n\n"
    answer += f"Custo total: **${top_cost:,.2f}**\n\n"
    answer += f"**Top 10 serviços por custo total{period_info}:**"

    return ChatResponse(
        answer_text=answer,
        dataframe=result_df.to_dict("records")
    )


def _analyze_total_cost(user_query: str, cost_df: pd.DataFrame) -> ChatResponse:
    """Analisa custo total."""
    filtered_df = _filter_by_period(user_query, cost_df)

    if TOTAL_COLUMN in filtered_df.columns:
        total = filtered_df[TOTAL_COLUMN].sum()
    else:
        service_cols = [col for col in filtered_df.columns if col != DATE_COLUMN]
        total = filtered_df[service_cols].sum().sum()

    result_df = pd.DataFrame([{"Custo Total": f"${total:,.2f}"}])

    answer = f"**Custo total no período:** ${total:,.2f}"

    return ChatResponse(
        answer_text=answer,
        dataframe=result_df.to_dict("records")
    )


def _analyze_period(user_query: str, cost_df: pd.DataFrame) -> ChatResponse:
    """Analisa dados de um período específico."""
    filtered_df = _filter_by_period(user_query, cost_df)

    if filtered_df.empty:
        return ChatResponse(answer_text="⚠️ Nenhum dado encontrado para o período especificado.")

    # Resumo do período
    if TOTAL_COLUMN in filtered_df.columns:
        total = filtered_df[TOTAL_COLUMN].sum()
    else:
        service_cols = [col for col in filtered_df.columns if col != DATE_COLUMN]
        total = filtered_df[service_cols].sum().sum()

    service_cols = [col for col in filtered_df.columns if col not in [DATE_COLUMN, TOTAL_COLUMN]]
    top_services = filtered_df[service_cols].sum().sort_values(ascending=False).head(5)

    answer = f"**Análise do período:**\n\n"
    answer += f"- Total de registros: {len(filtered_df)}\n"
    answer += f"- Custo total: ${total:,.2f}\n\n"
    answer += "**Top 5 serviços no período:**\n"

    result_data = []
    for service, cost in top_services.items():
        if cost > 0:
            answer += f"- {service.replace('($)', '')}: ${cost:,.2f}\n"
            result_data.append({"Serviço": service.replace("($)", ""), "Custo": f"${cost:,.2f}"})

    result_df = pd.DataFrame(result_data)

    return ChatResponse(
        answer_text=answer,
        dataframe=result_df.to_dict("records")
    )


def _filter_by_period(user_query: str, cost_df: pd.DataFrame) -> pd.DataFrame:
    """Filtra DataFrame por período mencionado na pergunta."""
    if DATE_COLUMN not in cost_df.columns:
        return cost_df

    months = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
    }

    query_lower = user_query.lower()
    filtered_df = cost_df.copy()

    # Converter coluna de data
    try:
        filtered_df[DATE_COLUMN] = pd.to_datetime(filtered_df[DATE_COLUMN], errors="coerce")
    except Exception:
        return cost_df

    # Filtrar por mês
    for month_name, month_num in months.items():
        if month_name in query_lower:
            filtered_df = filtered_df[filtered_df[DATE_COLUMN].dt.month == month_num]
            break

    # Filtrar por ano se mencionado
    import re
    year_match = re.search(r"\b(20\d{2})\b", user_query)
    if year_match:
        year = int(year_match.group(1))
        filtered_df = filtered_df[filtered_df[DATE_COLUMN].dt.year == year]

    return filtered_df


def _build_data_context(df: pd.DataFrame) -> str:
    """Constrói contexto sobre os dados para o LLM."""
    context = f"DataFrame com {len(df)} linhas e {len(df.columns)} colunas.\n\n"
    context += "ESTRUTURA IMPORTANTE:\n"
    context += f"- Coluna de DATA: '{DATE_COLUMN}' (contém as datas dos períodos)\n"
    context += f"- Coluna de TOTAL: '{TOTAL_COLUMN}' (soma de todos os custos)\n"
    context += f"- Colunas de SERVIÇOS: {len([c for c in df.columns if c not in [DATE_COLUMN, TOTAL_COLUMN]])} colunas com custos por serviço\n\n"
    
    context += f"Todas as colunas: {', '.join(df.columns.tolist()[:10])}"
    if len(df.columns) > 10:
        context += f" ... e mais {len(df.columns) - 10} colunas\n"
    context += "\n"

    # Exemplo de dados
    if len(df) > 0:
        context += f"Exemplo de dados (primeiras 2 linhas, apenas algumas colunas):\n"
        sample_cols = [DATE_COLUMN] + [c for c in df.columns if c != DATE_COLUMN][:5]
        context += f"{df[sample_cols].head(2).to_string()}\n"

    return context


def _execute_safe_code(code: str, df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Executa código Pandas de forma segura.

    Args:
        code: Código Python a executar
        df: DataFrame de custos

    Returns:
        DataFrame resultante ou None
    """
    # Lista de operações permitidas
    allowed_names = {
        "pd": pd,
        "df": df.copy(),  # Usar cópia para não modificar original
        "DataFrame": pd.DataFrame,
        "sum": sum,
        "max": max,
        "min": min,
        "len": len,
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
    }

    # Remover imports e outras operações perigosas
    safe_code = code.strip()
    safe_code = re.sub(r"^import\s+.*$", "", safe_code, flags=re.MULTILINE)
    safe_code = re.sub(r"^from\s+.*$", "", safe_code, flags=re.MULTILINE)
    safe_code = re.sub(r"eval\s*\(", "", safe_code)
    safe_code = re.sub(r"exec\s*\(", "", safe_code)

    try:
        # Tentar compilar o código
        try:
            compiled = ast.parse(safe_code, mode="exec")
        except SyntaxError as e:
            raise ValueError(f"Erro de sintaxe no código: {str(e)}")

        # Verificar se há apenas operações seguras
        for node in ast.walk(compiled):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise ValueError("Imports não permitidos")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec", "__import__", "open", "file"]:
                    raise ValueError("Operações perigosas não permitidas")

        # Executar em namespace restrito
        namespace = {"__builtins__": {}}
        namespace.update(allowed_names)
        
        # Executar o código compilado - usar compile() para garantir formato correto
        code_obj = compile(compiled, "<string>", "exec")
        exec(code_obj, namespace)

        # Tentar encontrar resultado
        if "result" in namespace:
            result = namespace["result"]
            if isinstance(result, pd.DataFrame):
                return result
            elif isinstance(result, (int, float, str)):
                # Converter valor único para DataFrame
                return pd.DataFrame([{"resposta": result}])
            elif isinstance(result, (list, tuple)):
                # Tentar converter para DataFrame
                try:
                    return pd.DataFrame(result)
                except Exception:
                    return pd.DataFrame([{"resposta": str(result)}])
            elif isinstance(result, dict):
                # Tentar converter dict para DataFrame
                try:
                    return pd.DataFrame([result])
                except Exception:
                    return pd.DataFrame([{"resposta": str(result)}])

        # Verificar se df foi modificado e retornado
        if "df" in namespace:
            modified_df = namespace["df"]
            if isinstance(modified_df, pd.DataFrame) and not modified_df.equals(df):
                return modified_df

        return None
    except Exception as e:
        raise ValueError(f"Erro ao executar código: {str(e)}")


def _format_answer_with_result(llm_response: str, result_df: pd.DataFrame) -> str:
    """Formata a resposta incluindo o resultado do DataFrame."""
    # Extrair explicação do LLM (antes do código)
    explanation = llm_response.split("```python")[0].strip()
    
    # Adicionar resumo do resultado
    if len(result_df) == 1 and len(result_df.columns) == 1:
        # Resultado único
        value = result_df.iloc[0, 0]
        explanation += f"\n\n**Resultado:** {value}"
    elif len(result_df) <= 10:
        # Resultado pequeno - mostrar diretamente
        explanation += f"\n\n**Resultado:**\n{result_df.to_string(index=False)}"
    else:
        # Resultado grande - mostrar resumo
        explanation += f"\n\n**Resultado:** {len(result_df)} itens encontrados. Mostrando os primeiros 10:"
        explanation += f"\n{result_df.head(10).to_string(index=False)}"
    
    return explanation
