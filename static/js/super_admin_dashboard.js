// 最高管理者権限の譲渡確認
function confirmTransfer(userName) {
    return confirm(`${userName} に最高管理者権限を譲渡しますか？ これは元に戻せません。`);
}

// ソフトデリート時の文字入力確認
function confirmDeleteWithInput(userName) {
    const input = prompt(`${userName} を削除します。\n続行するには「削除」と入力してください。`);
    if (input === "削除") {
        return true;
    } else if (input === null) {
        // ユーザーがキャンセルを押した場合
        alert("削除をキャンセルしました。");
        return false;
    } else {
        alert("正しく「削除」と入力してください。削除は実行されません。");
        return false;
    }
}