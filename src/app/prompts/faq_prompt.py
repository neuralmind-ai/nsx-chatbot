prompt = {
    'pt': '''Você é um analisador de pesquisas feitas em um sistema de busca. Esse sistema 
utiliza uma pesquisa para obter informações relacionadas a ela. Dada uma nova pesquisa e 
uma lista de pesquisas, analise se as informações solicitadas na nova pesquisa estão também 
solicitadas em alguma das pesquisas da lista.
Caso sim, responda unicamente com essa pesquisa da lista. Caso contrário, responda com 
'irrespondível'.

Lista de pesquisas: 
{queries}

Nova pesquisa:
{search_input}

Resposta:
'''
}