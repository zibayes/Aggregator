from agregator.chroma import CHROMA_PATH, get_embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores.chroma import Chroma
import os
import re
import psycopg2
from duckduckgo_search import DDGS
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
from .query_templates import DB_QUERY_TEMPLATE, SOURCE_TEMPLATE, RESULT_TEMPLATE, \
    PROMPT_TEMPLATE, INFO_SOURCES, REFORMULATE_TEMPLATE, SIMPLE_QUESTION_TEMPLATE, INTERNET_QUERY_TEMPLATE


def ddg_search(query):
    results = DDGS().text(query, region='ru-ru', safesearch='off', timelimit='y', max_results=2)
    print(results)
    urls = []
    for result in results:
        url = result['href']
        urls.append(url)

    docs = get_page(urls)

    content = []
    for doc in docs:
        page_text = re.sub("\n\n+", "\n", doc.page_content)
        text = truncate(page_text)
        content.append(text)

    return content


def get_page(urls):
    loader = AsyncChromiumLoader(urls)
    html = loader.load()

    bs_transformer = BeautifulSoupTransformer()
    docs_transformed = bs_transformer.transform_documents(html, tags_to_extract=["p"], remove_unwanted_tags=["a"])

    return docs_transformed


def truncate(text):
    words = text.split()
    truncated = " ".join(words[:400])

    return truncated


def ask_question_with_context(query_text: str) -> str:
    db = Chroma(persist_directory=os.path.join(os.getcwd(), CHROMA_PATH), embedding_function=get_embeddings())
    model = ChatOpenAI(temperature=0.7, base_url="http://localhost:1234/v1", api_key="not-needed")

    vectorstore = Chroma(embedding_function=get_embeddings(), persist_directory=os.path.join(os.getcwd(), CHROMA_PATH))
    # documents = vectorstore.get()
    # bm25_retriever = BM25Retriever(vectorstore=db, docs=documents)
    vectorstore_retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    prompt_template = ChatPromptTemplate.from_template(SOURCE_TEMPLATE)
    prompt = prompt_template.format(question=query_text)
    response_text = model.invoke(prompt)
    response_text = [text.strip() for text in response_text.content.replace('-', '').split('\n') if text]
    print(response_text)
    if any([text in INFO_SOURCES for text in response_text]):
        if 'реляционная база данных' in response_text:
            prompt_template = ChatPromptTemplate.from_template(DB_QUERY_TEMPLATE)
            prompt = prompt_template.format(question=query_text)
            response_text = model.invoke(prompt)
            response_text = response_text.content.replace('```sql', '').replace('```', '').strip()
            print(response_text)

            db_config = {
                'dbname': 'postgres',  # имя базы данных
                'user': 'postgres',  # имя пользователя
                'password': 'admin',  # пароль
                'host': 'localhost',  # хост (например, localhost)
                'port': '5432'  # порт (по умолчанию 5432)
            }
            try:
                connection = psycopg2.connect(**db_config)
                cursor = connection.cursor()
                cursor.execute(response_text)
                db_response = cursor.fetchall()
                if db_response:
                    for row in db_response:
                        print(row)
                else:
                    print('!', db_response)
            except Exception as e:
                print(f"Ошибка: {e}")
                db_response = e
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()

            prompt_template = ChatPromptTemplate.from_template(RESULT_TEMPLATE)
            prompt = prompt_template.format(question=query_text, db_response=db_response)
            response_text = model.invoke(prompt)
            print(response_text.content)
        elif 'векторная база данных' in response_text:
            prompt_template = ChatPromptTemplate.from_template(REFORMULATE_TEMPLATE)
            prompt = prompt_template.format(question=query_text)
            response_text = model.invoke(prompt)
            reformulated_prompts = [prompt] + [prompt.replace('*', '') for prompt in response_text.content.split('\n')
                                               if
                                               prompt]
            print(f"Полученные переформулированные промпты: {reformulated_prompts}")

            for ref_prompt in reformulated_prompts:
                # ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, vectorstore_retriever], weights=[0.5, 0.5])
                # results = ensemble_retriever.get_relevant_documents(ref_prompt)
                # results = vectorstore_retriever.get_relevant_documents(ref_prompt)
                results = db.similarity_search_with_relevance_scores(query_text, k=5)
                if len(results) == 0:
                    response = f"Нет фрагментов текста, на которые можно опираться для ответа."
                    print(response)
                    return response

                context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
                prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
                prompt = prompt_template.format(context=context_text, question=query_text)
                # print(f"Полученный промпт {prompt}")

                response_text = model.invoke(prompt)
                return response_text.content

                sources = [doc.metadata.get("source", None) for doc, _score in results]
                formatted_response = f"Ответ: {response_text}\nДанные взяты из: {sources}"
                print(formatted_response)
        elif 'выход в интернет' in response_text:
            prompt_template = ChatPromptTemplate.from_template(INTERNET_QUERY_TEMPLATE)
            prompt = prompt_template.format(question=query_text)
            response_text = model.invoke(prompt)
            print(response_text.content)
            context_text = "\n\n---\n\n".join(ddg_search(query_text))
            print(context_text)

            prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
            prompt = prompt_template.format(context=context_text, question=query_text)
            response_text = model.invoke(prompt)
        elif 'источник информации не требуется' in response_text:
            prompt_template = ChatPromptTemplate.from_template(SIMPLE_QUESTION_TEMPLATE)
            prompt = prompt_template.format(question=query_text)
            response_text = model.invoke(prompt)

        return response_text.content


if __name__ == "__main__":
    query_text = input('Введите запрос: ')
    ask_question_with_context(query_text)
