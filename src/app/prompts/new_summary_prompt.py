prompt = {
    "pt": """Seu objetivo é resumir uma conversa de modo claro e conciso para um assistente de
chat. Aja como se estivesse diretamente contextualizando o assistente sobre a conversa.

Resumo de conversas anteriores: {old_summary}
Novas informações do chat: {interactions}

Responda com um novo resumo combinando o resumo de conversas anteriores com as novas informações do chat, se essas
forem relevantes. Esse novo resumo deve ser sucinto e escrito em poucas frases, priorizando principalmente informações
sobre o usuário, informações fornecidas por ele e os principais assuntos da conversa.
"""
}
