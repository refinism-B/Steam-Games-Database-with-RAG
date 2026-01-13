document.addEventListener('DOMContentLoaded', function () {
  // 延遲 1 秒後模擬點擊側邊欄的 Readme 按鈕
  setTimeout(function () {
    var readmeButton = document.getElementById('readme-button');
    if (readmeButton) {
      readmeButton.click();
    }
  }, 1000); 
});