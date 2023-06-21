from app.prompts import chat_prompt
from app.prompts import faq_prompt
from app.prompts import new_summary_prompt
from app.prompts import answer_not_found
from app.prompts import unanswerable_search
from app.prompts import forced_finish

prompts = {
    'pt': {
        'chat_prompt': chat_prompt.prompt['pt'],
        'answer_not_found': answer_not_found.prompt['pt'],
        'unanswerable_search': unanswerable_search.prompt['pt'],
        'forced_finish': forced_finish.prompt['pt'],
        'faq_prompt': faq_prompt.prompt['pt'],
        'new_summary_prompt': new_summary_prompt.prompt['pt'],
    }
}