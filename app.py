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

    should_show_rag = settings["Show_RAG"]

    # 2. 建立訊息物件，準備串流顯示
    msg = cl.Message(content="", author="Steam RAG Bot")
    await msg.send()

    # 3. 呼叫後端的非同步版本 async_chat_generator
    generator = bot.async_chat_generator(
        message.content, display_data=should_show_rag)

    try:
        # 使用非同步迭代器接收串流
        async for chunk in generator:
            print(f"🔹 [前端收到 chunk]: {repr(chunk[:100]) if len(chunk) > 100 else repr(chunk)}")
            
            # 跳過空字串
            if not chunk or (isinstance(chunk, str) and not chunk.strip()):
                continue
                
            # 跳過工具執行訊息（暫時不顯示）
            if chunk.startswith("[執行]") or chunk.startswith("[結果]"):
                continue

            # 使用 stream_token 即時逐字顯示
            await msg.stream_token(chunk)
            print(f"📨 [串流傳送]: {len(chunk)} 字元")

    except Exception as e:
        print(f"❌ [發生錯誤]: {e}")
        await msg.stream_token(f"\n\n\n⚠️ **系統發生錯誤**：{str(e)}")
    
    # 完成串流，更新最終訊息
    await msg.update()
    
    if msg.content:
        print(f"✅ [訊息已發送] 內容長度: {len(msg.content)}")
    else:
        # 若無內容，發送提示訊息
        msg.content = "⚠️ 系統未能產生回應，請重新嘗試。"
        await msg.update()
        print("⚠️ [無內容可發送]")
