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
            values=["free/Gemini 3 flash",
                    "local/Gemma 3 12B", "price/Gemini 3 flash"],
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
        await cl.Message(content=f"✅ 系統設定已更新：目前切換至 {settings['Model']}").send()
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
    
    should_show_rag = settings["Show_RAG"]

    # 2. 建立一個空的訊息容器用於串流輸出
    msg = cl.Message(content="", author="Steam RAG Bot")

    # 3. 呼叫後端的 chat_generator
    # 注意：display_data 對應 settings["Show_RAG"]
    generator = bot.chat_generator(
        message.content, display_data=should_show_rag)

    current_step = None

    try:
        for chunk in generator:
            if chunk.startswith("[執行]") or chunk.startswith("[結果]"):
                if should_show_rag:
                    if chunk.startswith("[執行]"):
                        current_step = cl.Step(name="正在檢索資料...", type="tool")
                        await current_step.__aenter__()
                        # 使用程式碼塊，配合 CSS 即可自動換行
                        await current_step.stream_token(f"```python\n{chunk.replace('[執行]: ', '')}\n```")
                    else:
                        await current_step.stream_token(f"\n**檢索結果：**\n```text\n{chunk.replace('[結果]: ', '')}\n```")
                        await current_step.__aexit__(None, None, None)
                continue

            # 處理一般對話內容的串流
            if not msg.content:
                await msg.send()
            await msg.stream_token(chunk)
    except Exception as e:
        if not msg.content:
             await msg.send()
        await msg.stream_token(f"\n\n\n⚠️ **系統發生錯誤**：{str(e)}")


    await msg.update()
