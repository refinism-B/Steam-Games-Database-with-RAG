import chainlit as cl
from chainlit.input_widget import Select, Switch
from src.llm.llm import init_bot


USER_AVATAR = "public/avatars/User.png"
BOT_AVATAR = "public/avatars/Steam RAG Bot.png"


@cl.on_chat_start
async def start():
    # 初始化設定選單
    settings = await cl.ChatSettings([
        Select(
            id="Model",
            label="選擇使用模型",
            values=["free/Gemini 3 flash", "price/Gemini 3 flash",
                    "price/ChatGPT 4o mini", "local/Gemma 3 12B"],
            initial_index=0,
        ),
        Switch(
            id="Show_RAG",
            label="是否顯示檢索與思考過程",
            initial=True  # 改為預設開啟
        ),
    ]).send()

    # 先保存設定，確保即使 bot 初始化失敗，設定按鈕仍然可見
    cl.user_session.set("settings", settings)

    # 嘗試初始化 Bot，若失敗則通知使用者
    try:
        bot = init_bot(settings["Model"])
        cl.user_session.set("bot", bot)
    except Exception as e:
        cl.user_session.set("bot", None)
        await cl.Message(
            content=f"⚠️ **系統初始化錯誤**\n\n無法初始化 LLM Bot，請檢查環境變數設定（API Keys、資料庫連線等）。\n\n錯誤訊息：`{str(e)}`"
        ).send()


@cl.on_settings_update
async def setup_agent(settings):
    """當使用者更改模型或設定時，重新初始化 Bot"""
    cl.user_session.set("settings", settings)

    # 重新根據新模型建立 Bot
    try:
        new_bot = init_bot(settings["Model"])
        cl.user_session.set("bot", new_bot)
        # await cl.Message(content=f"✅ 系統設定已更新：目前切換至 {settings['Model']}").send()
    except Exception as e:
        cl.user_session.set("bot", None)
        await cl.Message(
            content=f"⚠️ **模型切換失敗**\n\n無法初始化新的 LLM Bot。\n\n錯誤訊息：`{str(e)}`"
        ).send()


@cl.on_message
async def main(message: cl.Message):
    # 1. 取得 Session 中的 bot 與設定
    bot = cl.user_session.get("bot")
    settings = cl.user_session.get("settings")

    # 檢查 bot 是否成功初始化
    if bot is None:
        await cl.Message(
            content="⚠️ **Bot 尚未初始化**\n\n請檢查系統設定或重新整理頁面。若問題持續，請聯繫管理員。"
        ).send()
        return

    # 2. 初始化變數
    should_show_rag = settings["Show_RAG"]
    msg = None  # 延遲建立訊息物件
    thinking_buffer = ""
    BUFFER_THRESHOLD = 1500  # 思考緩衝區閾值

    # 3. 呼叫後端的非同步版本 async_chat_generator
    generator = bot.async_chat_generator(
        message.content, display_data=should_show_rag)

    # 追蹤當前 Step 狀態（用於工具調用顯示）
    current_step = None

    try:
        # 使用非同步迭代器接收串流
        async for chunk in generator:
            if not chunk:
                continue

            # 累積到緩衝區
            thinking_buffer += chunk

            # --- 邏輯分支 1: 偵測到「執行工具」 ---
            if "[執行]" in thinking_buffer:
                if should_show_rag:
                    # 分割思考過程與工具指令
                    split_index = thinking_buffer.find("[執行]")
                    thought_process = thinking_buffer[:split_index].strip()
                    tool_content = thinking_buffer[split_index:].strip()

                    # 處理工具資訊
                    tool_info = tool_content.replace(
                        "[執行]: ", "").replace("\n-----------\n", "")

                    # 建立 Step
                    current_step = cl.Step(name="資料檢索...", type="tool")

                    # 將思考過程與工具內容合併顯示
                    display_input = tool_info
                    if thought_process:
                        display_input = f"🤔 思考過程：\n{thought_process}\n\n🛠️ 呼叫工具：\n{tool_info}"

                    current_step.input = display_input
                    await current_step.send()
                    print(f"📋 [Step 建立]: {tool_info[:50]}...")

                # 清空緩衝區（已轉為 Step 內容）
                thinking_buffer = ""
                continue

            # --- 邏輯分支 2: 偵測到「執行結果」 ---
            if "[結果]" in thinking_buffer:
                if should_show_rag and current_step:
                    # 處理結果資訊
                    split_index = thinking_buffer.find("[結果]")
                    result_content = thinking_buffer[split_index:].replace(
                        "[結果]: ", "").replace("\n-----------\n", "")

                    current_step.output = f"```data\n{result_content}\n```"

                    # current_step.output = result_content
                    await current_step.update()
                    print(f"📋 [Step 更新]: 結果長度 {len(result_content)} 字元")
                    current_step = None

                # 清空緩衝區
                thinking_buffer = ""
                continue

            # --- 邏輯分支 3: 超過緩衝閾值（視為一般回應） ---
            if len(thinking_buffer) > BUFFER_THRESHOLD:
                # 建立訊息（如果尚未建立）
                if msg is None:
                    print(f"⚠️ 觸發閾值建立訊息！緩衝區長度: {len(thinking_buffer)}")
                    print(f"⚠️ 緩衝區內容預覽: {repr(thinking_buffer[:100])}")

                    msg = cl.Message(content="", author="Steam RAG Bot")
                    await msg.send()

                # 將緩衝區內容串流出去
                await msg.stream_token(thinking_buffer)
                thinking_buffer = ""

    except Exception as e:
        print(f"❌ [發生錯誤]: {e}")
        if msg is None:
            msg = cl.Message(content="", author="Steam RAG Bot")
            await msg.send()
        await msg.stream_token(f"\n\n\n⚠️ **系統發生錯誤**：{str(e)}")

    # 4. 迴圈結束後的清理工作
    # 若緩衝區仍有剩餘文字（例如簡短的最終回應），這時才顯示
    if thinking_buffer:
        if msg is None:
            msg = cl.Message(content="", author="Steam RAG Bot")
            await msg.send()
        await msg.stream_token(thinking_buffer)

    # 更新最終訊息狀態
    if msg:
        await msg.update()
    else:
        # 只有在完全沒有任何產出（也沒有 Step ？）時才視為無回應
        # 但若有 run step，msg 可能為 None，這時不應報錯，因為主要互動在 Step 中
        pass
