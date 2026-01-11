1. **資料擷取**
    透過訪問API的方式取得以下資料，並將原始資料存取為json檔案。
    1. app id: 透過Steam Web API端點，先取得Steam平台中所有遊戲的appid(steam平台上每一款遊戲的唯一id值)。
    2. game info: 將取得的appid列表輸入API端點，逐一查詢遊戲詳細資訊。
    3. game review: 將取得的appid列表輸入API端點，逐一查詢遊戲的評價資訊。
    4. game tag: 將取得的appid列表輸入Steam SPY的API端點，逐一查詢遊戲的標籤資訊。

2. **ETL流程**
    1. **資料合併**: 將game info, game review, game tag三類資料，根據相同appid(即代表是同一款遊戲)進行合併。
    2. **欄位清洗**: 將不需要存取的資料欄未去除。
    3. **攤平結構**: 將巢狀結構盡量攤平。
    4. **資料清洗**: 將描述性欄位中的html標籤及多於空格去除，還原成純文字資料。
    5. **結構重塑**: 將欄位分成兩類`context`（描述型內容，只保留字串）和`metadata`（標籤數值型內容，保留dict格式），並將原有的資料進行分類。

3. **text embedding**
    1. **建立Document物件**: 將處理完畢的json檔轉換成Document物件，`context`欄位資料放入`page_content`、`metadata`欄位資料放入`metadata`。
    2. **Parent-Document切割**: 將每筆文件進行Parent-Document切割，父層資料切割較粗、子層資料切割較細，並建立關聯。
    3. **去重複**: 輸入向量資料庫前進行去重複，確保沒有重複資料。
    4. **text embedding**: 使用`bge-3m`的model進行text embedding，並存入向量資料庫。

4. **LLM & RAG**
    1. **LLM連接**: 可連接雲端gemini-3-flash或介接地端Ollama/LM studio（測試時使用gemma-3-12b）。
    2. **RAG系統建立**: 建立Parent-Document RAG系統，並透過綁定及提示詞讓LLM需要時可以調用工具。
    3. **存取對話列表**: 添加對話列表儲存機制，實現具記憶性、可多輪對話的聊天機器人。