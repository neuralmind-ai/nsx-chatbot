from settings import settings

model = settings.reasoning_model
domain = 'vestibular'
prompt = f'''
your prompt
'''

functions = [{
  "name": "responder_pergunta",
  "description": "Responder pergunta sobre {domain} ".format(domain=domain),
  "parameters": {
      "type": "object",
      "properties": {
          "informacao": {
              "type": "string",
              "description": "informacao necessarias para responder a pergunta"
          }
      },
      "required": ["pergunta", "informacoes"]
  }
}]

stop = stop=[f"Observação 1:", "Mensagem:"]

