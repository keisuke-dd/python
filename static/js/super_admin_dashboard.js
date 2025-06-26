// 最高管理者権限の譲渡確認（文字入力）
function confirmTransferWithInput(userName) {
    const input = prompt(`${userName} に最高管理者権限を譲渡します。\n続行するには「譲渡」と入力してください。`);
    if (input === "譲渡") {
        return true;
    } else if (input === null) {
        alert("譲渡をキャンセルしました。");
        return false;
    } else {
        alert("正しく「譲渡」と入力してください。操作は中止されました。");
        return false;
    }
}

// ソフトデリート時の文字入力確認
function confirmDeleteWithInput(userName) {
    const input = prompt(`${userName} を削除します。\n続行するには「削除」と入力してください。`);
    if (input === "削除") {
        return true;
    } else if (input === null) {
        alert("削除をキャンセルしました。");
        return false;
    } else {
        alert("正しく「削除」と入力してください。削除は実行されません。");
        return false;
    }
}