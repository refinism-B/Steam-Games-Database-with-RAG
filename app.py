import chainlit as cl
from chainlit.input_widget import Select, Switch


def my_steam_llm_logic(user_input: str, model: str):
    """
    這是一個佔位函數，請在這裡呼叫你原本的 RAG 程式碼。
    回傳值可以是字串（回答內容）。
    """
    # 這裡實作你的檢索與生成邏輯
    # 範例：return your_rag_engine.query(user_input, model=model)
    return f"【使用 {model} 回覆】關於「{user_input}」：這是一款在 Steam 上評價極高的遊戲..."


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
            initial=False
        ),
    ]).send()

    cl.user_session.set("settings", settings)

    # 發送歡迎訊息
    # await cl.Message(
    #     content="🎮 你好！請直接輸入你想查詢的 Steam 遊戲名稱或相關問題..."
    # ).send()


@cl.on_settings_update
async def setup_agent(settings):
    """當使用者在 UI 更改設定時觸發"""
    cl.user_session.set("settings", settings)
    await cl.Message(content=f"系統設定已更新：目前使用 {settings['Model']}").send()


@cl.on_message
async def main(message: cl.Message):
    # 1. 取得當前使用者設定
    settings = cl.user_session.get("settings")
    current_model = settings["Model"]
    should_show_rag = settings["Show_RAG"]

    # 2. 如果開關開啟，顯示 RAG 檢索過程 (cl.Step)
    if should_show_rag:
        async with cl.Step(name="Steam RAG Engine", type="tool") as step:
            step.input = message.content
            # 這裡可以放你檢索資料庫的過程描述
            step.output = f"正在從 Steam 資料庫檢索「{message.content}」的評論與硬體需求..."

    # 3. 呼叫你的 LLM 邏輯
    # 這裡我們模擬一個非同步呼叫，或是直接執行你的函數
    final_answer = my_steam_llm_logic(message.content, current_model)

    # 4. 回傳最終答案給使用者
    await cl.Message(content=final_answer).send()
