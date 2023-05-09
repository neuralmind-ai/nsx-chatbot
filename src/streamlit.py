import streamlit as st
from app.services.chat_handler import ChatHandler

# Includes the message in the chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = ""

# dropdown with options
dropdown = st.sidebar.selectbox(
    "Escolha o índice",
    (
        "FUNDEP_Ciencias",
        "FUNDEP_Medicina",
        "FUNDEP_Pneumologia",
        "FUNDEP_Paraopeba",
        "FUNDEP_Cardiologia",
    ),
)

# Checkbox for verbose
verbose = st.sidebar.checkbox("Verbose")

user_id = st.sidebar.text_input("Id do usuário")

chatbot = ChatHandler(verbose=verbose, return_debug=verbose)

st.title("Fundep Debug")

# Button to clear the chat history
clear_chat = st.button("Limpar texto")

text_area = st.empty()

message_input = st.text_input("Escreva uma mensagem")

if message_input and not clear_chat:
    answer = chatbot.get_response(message_input, str(user_id))

    if "chat_history" in st.session_state:
        st.session_state.chat_history = (
            f"{st.session_state.chat_history}\n\nVocê: {message_input}\nBot: {answer}"
        )

        # Displays the chat history
        text_area.text(st.session_state.chat_history)

if clear_chat:
    if "chat_history" in st.session_state:
        st.session_state.chat_history = ""
