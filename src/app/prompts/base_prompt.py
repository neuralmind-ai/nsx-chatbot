from app.prompts import (
    answer_not_found,
    chat_prompt,
    faq_prompt,
    forced_finish,
    new_summary_prompt,
    unanswerable_search,
)

prompts = {
    "pt": {
        "chat_prompt": chat_prompt.prompt["pt"],
        "answer_not_found": answer_not_found.prompt["pt"],
        "unanswerable_search": unanswerable_search.prompt["pt"],
        "forced_finish": forced_finish.prompt["pt"],
        "faq_prompt": faq_prompt.prompt["pt"],
        "new_summary_prompt": new_summary_prompt.prompt["pt"],
    }
}
