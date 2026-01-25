import asyncio
import os

# import psycopg2
from langchain.embeddings.base import Embeddings
from langchain.messages import (AIMessage, AIMessageChunk, HumanMessage,
                                SystemMessage, ToolMessage)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langchain_huggingface import HuggingFaceEndpointEmbeddings
# from langchain_ollama import OllamaEmbeddings
from langchain_openai import ChatOpenAI
from langchain_postgres.vectorstores import DistanceStrategy, PGVector
from openai import APIConnectionError, OpenAI

from src.config.constant import (LM_STUDIO_IP, PG_COLLECTION, SYSTEM_PROMPT,
                                 TEI_URL)
from src.database import postgreSQL_conn as pgc
from src.rag.tools import create_few_game_rag_tool

# EMBEDDING_MODEL, OLLAMA_LOCAL, OLLAMA_URL, PROJECT_ROOT


"""
建立連線
"""
# 建立embedding連線
# embeddings = OllamaEmbeddings(
#     model=EMBEDDING_MODEL,
#     base_url=OLLAMA_URL
# )

embeddings = HuggingFaceEndpointEmbeddings(
    model=TEI_URL,
)

# 載入向量資料庫
pg_url = pgc.connect_to_pgSQL()
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=PG_COLLECTION,
    connection=pg_url,
    use_jsonb=True,
    distance_strategy=DistanceStrategy.COSINE
)


# 建立embedding類別
class LmStudioEmbeddings(Embeddings):
    def __init__(self, model_name, url):
        self.model_name = model_name
        self.url = url
        self.client = OpenAI(base_url=url, api_key="lm-studio")

    def embed_query(self, text: str):
        response = self.client.embeddings.create(
            input=text, model=self.model_name)
        return response.data[0].embedding

    def embed_documents(self, texts: list[str]):
        # 回傳多個文件的 embedding
        response = self.client.embeddings.create(
            input=texts, model=self.model_name)
        return [x.embedding for x in response.data]
        # return [self.model.encode(t).tolist() for t in texts]


"""
選擇主要LLM
"""


def get_llm(model_option: str):
    """根據前端選擇回傳對應的 LLM 實例"""
    if "local/Gemma 3 12B" in model_option:
        return ChatOpenAI(
            model='gemma-3-12b-it',
            openai_api_key="not-needed",
            openai_api_base=LM_STUDIO_IP
        )
    elif "free/Gemini 3 flash" in model_option:
        return ChatGoogleGenerativeAI(
            model='gemini-3-flash-preview',
            google_api_key=os.getenv("GOOGLE_API")
        )
    elif "price/Gemini 3 flash" in model_option:
        return ChatGoogleGenerativeAI(
            model='gemini-3-flash-preview',
            google_api_key=os.getenv("GOOGLE_API_PRICE")
        )
    elif "price/ChatGPT 4o mini" in model_option:
        return ChatOpenAI(
            model='gpt-4o-mini',
            openai_api_key=os.getenv("OPENAI_API")
        )
    return None


def init_bot(model_option: str):
    llm = get_llm(model_option)
    few_game_rag = create_few_game_rag_tool(vector_store)
    tools = [few_game_rag]
    return stream_chat_bot(llm, tools)


"""
定義類別及流程
"""


class stream_chat_bot:
    def __init__(self, llm, tools):
        self.llm = llm
        # 初始化對話機器人，傳入 LLM 與可用工具列表
        self.tools = tools
        # 建立工具名稱對應表，用於後續動態呼叫
        self.tool_map = {tool.name: tool for tool in tools}

        # 將 LLM 綁定（bind）工具，使其具備自動呼叫工具的能力
        self.llm_with_tools = llm.bind_tools(tools)

        # 系統提示詞（System Prompt），用來設定 LLM 的角色與行為
        self.system_prompt_content = SYSTEM_PROMPT
        # 初始化訊息列表，第一條訊息是系統指令
        self.message = [SystemMessage(self.system_prompt_content)]

        # 將 LLM 的回應解析為純文字格式的工具
        self.str_parser = StrOutputParser()

    def _get_clean_history_for_auxiliary_llm(self, messages):
        """
        為輔助 LLM 函式建立乾淨的對話歷史，
        移除 tool_calls 相關內容以避免違反 Gemini API 順序規則。

        Gemini API 要求：Tool Call 必須緊接在 User 訊息或 Function Response 之後。
        因此輔助函式（如 rephrase、summarize）不應傳入包含 tool_calls 的對話歷史。
        """
        clean_messages = []
        for msg in messages:
            if isinstance(msg, (AIMessage, AIMessageChunk)):
                # 只保留純文字內容，移除 tool_calls
                if msg.content:
                    clean_messages.append(AIMessage(content=msg.content))
            elif isinstance(msg, ToolMessage):
                # 跳過 ToolMessage，因為輔助函式不需要工具執行結果
                continue
            else:
                # HumanMessage, SystemMessage 直接保留
                clean_messages.append(msg)
        return clean_messages

    def _rephrase_query(self, user_input):
        """
        中間層 LLM：將使用者原始輸入轉換為更精準的查詢語句。
        """
        rephrase_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一個提問優化專家。請分析使用者的輸入與對話歷史，
            將其轉換為一個『獨立、完整、精準且簡潔』的問題，以便讓後續的搜尋系統能精確執行。

            規則：
            1. 保留所有關鍵資訊（如：遊戲名稱、日期、特定術語）。
            2. 修復錯字或語意不明之處。
            3. 如果使用者使用了代名詞（如：他、這件事），請根據歷史紀錄替換成具體內容。
            4. 直接輸出優化後的提問文字，不要包含額外的解釋。"""),
            # 傳入部分歷史紀錄增加上下文理解力
            ("placeholder", "{history}"),
            ("human", "{input}")
        ])

        # 使用原始 LLM 進行快速轉換
        rephrase_chain = rephrase_prompt | self.llm | self.str_parser

        # 取最近的 3 條紀錄作為參考，並清理 tool_calls 相關內容
        raw_history = self.message[-3:] if len(self.message) > 1 else []
        history_context = self._get_clean_history_for_auxiliary_llm(
            raw_history)

        refined_query = rephrase_chain.invoke({
            "history": history_context,
            "input": user_input
        })

        # 限制查詢長度，防止 HuggingFaceEndpointEmbeddings 返回 413 錯誤
        max_query_length = 500
        if len(refined_query) > max_query_length:
            refined_query = refined_query[:max_query_length]

        return refined_query

    def _summarize_history(self):
        """
        執行摘要邏輯：保留 System Prompt 與最新的 2 條訊息，
        將其餘的歷史紀錄壓縮成一段摘要。
        """
        if not hasattr(self, 'system_prompt_content'):
            self.system_prompt_content = SYSTEM_PROMPT

        if len(self.message) <= 3:
            return

        keep_latest = 2
        to_summarize = self.message[1:-keep_latest]
        recent_messages = self.message[-keep_latest:]

        # 清理要摘要的訊息，移除 tool_calls 相關內容
        clean_to_summarize = self._get_clean_history_for_auxiliary_llm(
            to_summarize)

        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一個專業的對話秘書。請將下方的對話紀錄精簡壓縮，保留核心重點，減少約 30% 總長度，並以繁體中文撰寫。"),
            ("placeholder", "{content}")
        ])

        summary_chain = summary_prompt | self.llm | self.str_parser
        summary_text = summary_chain.invoke({"content": clean_to_summarize})

        # 重建訊息列表時，也清理最近的訊息
        clean_recent_messages = self._get_clean_history_for_auxiliary_llm(
            recent_messages)

        self.message = [
            SystemMessage(content=self.system_prompt_content),
            HumanMessage(content=f"這是先前的對話摘要：{summary_text}"),
            *clean_recent_messages
        ]
        print(f"\n✨ [系統通知]: 歷史紀錄已精簡完成。")

    def chat_generator(self, text, display_data=False):
        """
        主對話生成函式（生成器形式）。
        逐步執行 LLM 回應與工具調用，並即時回傳每一步的結果。
        """
        try:
            # 若對話紀錄超過 3 輪（約 8 則訊息），進行摘要
            if len(self.message) > 8:
                self._summarize_history()

            # 進行問題轉譯
            refined_text = self._rephrase_query(text)

            # 將轉役內容加入訊息列表
            self.message.append(HumanMessage(refined_text))

            while True:
                # 呼叫 LLM，傳入完整訊息歷史
                print(f"🔄 [LLM 呼叫開始] 訊息數量: {len(self.message)}")
                final_ai_message = AIMessageChunk(content="")
                for chunk in self.llm_with_tools.stream(self.message):
                    final_ai_message += chunk
                    if hasattr(chunk, 'content') and chunk.content:
                        # 處理 Gemini API 回傳 list 格式的 content
                        content = chunk.content
                        if isinstance(content, list):
                            # 提取 list 中的 text 欄位
                            text_parts = [
                                part.get('text', '') for part in content 
                                if isinstance(part, dict) and 'text' in part
                            ]
                            content = ''.join(text_parts)
                        if content:
                            yield content

                print(f"✅ [LLM 回應完成] 內容長度: {len(final_ai_message.content)}, 工具呼叫數: {len(final_ai_message.tool_calls)}")
                print(f"📝 [回應內容預覽]: {repr(final_ai_message.content[:200]) if final_ai_message.content else '(空)'}")

                response = final_ai_message

                # 將 LLM 回應加入訊息列表
                self.message.append(response)

                # 檢查 LLM 是否要求呼叫工具
                is_tools_call = False
                for tool_call in response.tool_calls:
                    is_tools_call = True

                    if display_data:
                        # # 顯示 LLM 要執行的工具名稱與參數
                        # 完整訊息
                        msg = f'[執行]: {tool_call["name"]}({tool_call["args"]})\n-----------\n'
                        yield msg  # 使用 yield 讓結果能即時顯示在輸出中

                    # 實際執行工具（根據工具名稱動態呼叫對應物件）
                    if tool_call['name'] in self.tool_map:
                        tool_result = self.tool_map[tool_call['name']].invoke(
                            tool_call['args'])
                    else:
                        tool_result = f"Error: Tool '{tool_call['name']}' not found."

                    if display_data:
                        # # 顯示工具執行結果
                        msg = f'[結果]: {tool_result}\n-----------\n'
                        yield msg

                    # 將工具執行結果封裝成 ToolMessage 回傳給 LLM
                    # 限制工具結果長度，防止超過 LLM token 限制
                    tool_result_str = str(tool_result)
                    max_tool_result_length = 8000
                    if len(tool_result_str) > max_tool_result_length:
                        tool_result_str = tool_result_str[:max_tool_result_length] + "\n...(結果已截斷)"
                        print(f"⚠️ [工具結果過長，已截斷至 {max_tool_result_length} 字元]")

                    tool_message = ToolMessage(
                        content=tool_result_str,               # 工具執行的文字結果
                        name=tool_call["name"],                # 工具名稱
                        # 工具呼叫 ID（讓 LLM 知道對應哪個呼叫）
                        tool_call_id=tool_call["id"],
                    )
                    # 將工具回傳結果加入訊息列表，提供 LLM 下一輪參考
                    self.message.append(tool_message)
                    print(f"✅ [工具執行完成]: {tool_call['name']}, 結果長度: {len(tool_result_str)} 字元")

                # 若這一輪沒有任何工具呼叫，表示 LLM 已經生成最終回覆
                if not is_tools_call:
                    break

        except ChatGoogleGenerativeAIError as e:
            # 處理 Google Gemini Token 耗盡 (429 RESOURCE_EXHAUSTED)
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                yield "API額度已耗盡，請更換其他模型"
                return
            raise e
        except APIConnectionError:
            # 處理 Local LLM 連線失敗
            yield "本地端伺服器無法連接，請更換其他模型"
            return

    async def _async_rephrase_query(self, user_input):
        """
        非同步版本：將使用者原始輸入轉換為更精準的查詢語句。
        """
        rephrase_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一個提問優化專家。請分析使用者的輸入與對話歷史，
            將其轉換為一個『獨立、完整、精準且簡潔』的問題，以便讓後續的搜尋系統能精確執行。

            規則：
            1. 保留所有關鍵資訊（如：遊戲名稱、日期、特定術語）。
            2. 修復錯字或語意不明之處。
            3. 如果使用者使用了代名詞（如：他、這件事），請根據歷史紀錄替換成具體內容。
            4. 直接輸出優化後的提問文字，不要包含額外的解釋。"""),
            ("placeholder", "{history}"),
            ("human", "{input}")
        ])

        rephrase_chain = rephrase_prompt | self.llm | self.str_parser

        raw_history = self.message[-3:] if len(self.message) > 1 else []
        history_context = self._get_clean_history_for_auxiliary_llm(raw_history)

        # 使用非同步呼叫
        refined_query = await rephrase_chain.ainvoke({
            "history": history_context,
            "input": user_input
        })

        max_query_length = 500
        if len(refined_query) > max_query_length:
            refined_query = refined_query[:max_query_length]

        return refined_query

    async def _async_summarize_history(self):
        """
        非同步版本：執行摘要邏輯，保留 System Prompt 與最新的 2 條訊息。
        """
        if not hasattr(self, 'system_prompt_content'):
            self.system_prompt_content = SYSTEM_PROMPT

        if len(self.message) <= 3:
            return

        keep_latest = 2
        to_summarize = self.message[1:-keep_latest]
        recent_messages = self.message[-keep_latest:]

        clean_to_summarize = self._get_clean_history_for_auxiliary_llm(to_summarize)

        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一個專業的對話秘書。請將下方的對話紀錄精簡壓縮，保留核心重點，減少約 30% 總長度，並以繁體中文撰寫。"),
            ("placeholder", "{content}")
        ])

        summary_chain = summary_prompt | self.llm | self.str_parser
        # 使用非同步呼叫
        summary_text = await summary_chain.ainvoke({"content": clean_to_summarize})

        clean_recent_messages = self._get_clean_history_for_auxiliary_llm(recent_messages)

        self.message = [
            SystemMessage(content=self.system_prompt_content),
            HumanMessage(content=f"這是先前的對話摘要：{summary_text}"),
            *clean_recent_messages
        ]
        print(f"\n✨ [系統通知]: 歷史紀錄已精簡完成。")

    async def async_chat_generator(self, text, display_data=False):
        """
        非同步版本的對話生成函式（Async Generator）。
        避免阻塞 Event Loop，確保 WebSocket 心跳正常。
        """
        try:
            # 若對話紀錄超過 3 輪（約 8 則訊息），進行摘要
            if len(self.message) > 8:
                await self._async_summarize_history()

            # 進行問題轉譯（非同步）
            refined_text = await self._async_rephrase_query(text)

            # 將轉譯內容加入訊息列表
            self.message.append(HumanMessage(refined_text))

            while True:
                # 呼叫 LLM，傳入完整訊息歷史（非同步串流）
                print(f"🔄 [LLM 呼叫開始] 訊息數量: {len(self.message)}")
                final_ai_message = AIMessageChunk(content="")
                
                # 用於緩衝內容，避免在工具呼叫時顯示「思考中」的文字
                content_buffer = []
                is_tool_turn = False
                stream_started = False
                BUFFER_THRESHOLD = 50  # 緩衝字元數閾值

                # 使用 astream 非同步串流
                async for chunk in self.llm_with_tools.astream(self.message):
                    final_ai_message += chunk
                    
                    # 檢查是否有工具呼叫
                    if chunk.tool_call_chunks or chunk.tool_calls:
                        is_tool_turn = True
                        # 若確定是工具呼叫，且尚未開始串流顯示，則清空緩衝區（隱藏思考文字）
                        if not stream_started:
                            content_buffer = []
                    
                    # 處理內容
                    if hasattr(chunk, 'content') and chunk.content:
                        content = chunk.content
                        if isinstance(content, list):
                            text_parts = [
                                part.get('text', '') for part in content 
                                if isinstance(part, dict) and 'text' in part
                            ]
                            content = ''.join(text_parts)
                        
                        if content:
                            if is_tool_turn:
                                # 若已知是工具呼叫回合，且之前沒開始輸出，則忽略內容
                                if not stream_started:
                                    continue
                                else:
                                    # 若已經開始輸出（極少見情況），只好繼續輸出
                                    yield content
                            else:
                                # 尚未確認是否為工具回合
                                if stream_started:
                                    # 已經認定是回答，直接輸出
                                    yield content
                                else:
                                    # 加入緩衝區
                                    content_buffer.append(content)
                                    current_buffer_len = sum(len(c) for c in content_buffer)
                                    
                                    # 若緩衝區超過閾值，認定為正式回答，開始輸出
                                    if current_buffer_len > BUFFER_THRESHOLD:
                                        stream_started = True
                                        for c in content_buffer:
                                            yield c
                                        content_buffer = []

                # 迴圈結束後，檢查是否還有緩衝內容
                if not is_tool_turn and content_buffer:
                    for c in content_buffer:
                        yield c

                print(f"✅ [LLM 回應完成] 內容長度: {len(final_ai_message.content)}, 工具呼叫數: {len(final_ai_message.tool_calls)}")
                print(f"📝 [回應內容預覽]: {repr(final_ai_message.content[:200]) if final_ai_message.content else '(空)'}")

                response = final_ai_message
                self.message.append(response)

                # 檢查 LLM 是否要求呼叫工具
                is_tools_call = False
                for tool_call in response.tool_calls:
                    is_tools_call = True

                    if display_data:
                        msg = f'[執行]: {tool_call["name"]}({tool_call["args"]})\n-----------\n'
                        yield msg

                    # 非同步執行工具
                    if tool_call['name'] in self.tool_map:
                        tool = self.tool_map[tool_call['name']]
                        # 優先使用 ainvoke，若不支援則用 to_thread 包裝
                        if hasattr(tool, 'ainvoke'):
                            tool_result = await tool.ainvoke(tool_call['args'])
                        else:
                            tool_result = await asyncio.to_thread(
                                tool.invoke, tool_call['args']
                            )
                    else:
                        tool_result = f"Error: Tool '{tool_call['name']}' not found."

                    if display_data:
                        msg = f'[結果]: {tool_result}\n-----------\n'
                        yield msg

                    tool_result_str = str(tool_result)
                    max_tool_result_length = 8000
                    if len(tool_result_str) > max_tool_result_length:
                        tool_result_str = tool_result_str[:max_tool_result_length] + "\n...(結果已截斷)"
                        print(f"⚠️ [工具結果過長，已截斷至 {max_tool_result_length} 字元]")

                    tool_message = ToolMessage(
                        content=tool_result_str,
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                    self.message.append(tool_message)
                    print(f"✅ [工具執行完成]: {tool_call['name']}, 結果長度: {len(tool_result_str)} 字元")

                if not is_tools_call:
                    break

        except ChatGoogleGenerativeAIError as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                yield "API額度已耗盡，請更換其他模型"
                return
            raise e
        except APIConnectionError:
            yield "本地端伺服器無法連接，請更換其他模型"
            return

    def chat(self, text, print_output=False):
        """
        封裝版對話函式。
        會收集 chat_generator 的所有輸出，並組合成完整的回覆字串。
        """
        msg = ''
        # 逐步取得 chat_generator 的產出內容
        for chunk in self.chat_generator(text):
            msg += f"{chunk}"
            if print_output:
                print(chunk, end='')
        # 回傳最終組合的對話內容
        return msg
