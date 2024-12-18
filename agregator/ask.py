from langchain_chroma import Chroma
from agregator.chroma import CHROMA_PATH, get_embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import os
from django.http import JsonResponse

PROMPT_TEMPLATE = """
Ответь на вопрос базируясь только на этом контексте:

{context}

---

Ответь на вопрос, используя только контекст: {question}
"""

def ask_question_with_context(query_text: str) -> str:
    # Создаем БД
    db = Chroma(persist_directory=os.path.join(os.getcwd(), CHROMA_PATH), embedding_function=get_embeddings())

    # Ищем по БД
    # Мы будем использовать 3 чанка из БД, которые наиболее похожи на наш вопрос
    # c этим количеством можете экспериментировать как угодно, главное, не переборщите, ваша LLM
    # должна поддерживать такое количество контекста, чтобы уместить весь полученный промпт
    results = db.similarity_search_with_relevance_scores(query_text, k=3)
    if len(results) == 0 or results[0][1] < 0.7:
        response = f"Нет фрагментов текста, на которые можно опираться для ответа."
        print(response)
        return response

    # Собираем запрос к LLM, объединяя наши чанки. Их мы записываем через пропуск строки и ---
    # помещаем мы контекст в переменную context, которую обозначали еще в самом промпте
    # ну и по аналогии вопрос просто записываем в переменную question.
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)
    print(f"Полученный промпт {prompt}")

    # Подключение к LM Studio и отправка запроса
    model = ChatOpenAI(temperature=0.7, base_url="http://localhost:1234/v1", api_key="not-needed")
    response_text = model.invoke(prompt)

    # Выводим результаты ответа
    sources = [doc.metadata.get("source", None) for doc, _score in results]
    formatted_response = f"Ответ: {response_text}\nДанные взяты из: {sources}"
    print(formatted_response)
    return response_text.content

if __name__ == "__main__":
    query_text = input('Введите запрос: ')
    ask_question_with_context(query_text)