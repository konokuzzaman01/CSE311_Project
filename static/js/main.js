
function showToast(message, type = "info") {
    const box = document.getElementById("toastBox");

    const div = document.createElement("div");
    div.classList.add("toast-msg");

    if (type === "success") div.style.background = "#2ecc71";
    else if (type === "error") div.style.background = "#e74c3c";

    div.innerText = message;

    box.appendChild(div);

    setTimeout(() => {
        div.remove();
    }, 3000);
}

function confirmDelete(url) {
    if (confirm("Are you sure you want to delete this record?")) {
        window.location.href = url;
    }
}

function tableSearch(inputId, tableId) {
    let filter = document.getElementById(inputId).value.toLowerCase();
    let rows = document.getElementById(tableId).getElementsByTagName("tr");

    for (let i = 1; i < rows.length; i++) {
        let text = rows[i].innerText.toLowerCase();
        rows[i].style.display = text.includes(filter) ? "" : "none";
    }
}

function downloadCSV(csvData, filename) {
    let blob = new Blob([csvData], { type: "text/csv" });
    let url = window.URL.createObjectURL(blob);

    let a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
}


document.addEventListener("DOMContentLoaded", function () {
    let flashMessages = document.querySelectorAll(".flash-msg");
    if (flashMessages.length > 0) {
        flashMessages.forEach(msg => {
            setTimeout(() => {
                msg.style.opacity = "0";
                setTimeout(() => msg.remove(), 500);
            }, 2500);
        });
    }
});


function highlightAttendance(rowId, status) {
    let row = document.getElementById(rowId);

    if (!row) return;

    row.querySelectorAll("td").forEach(td => td.style.background = "");

    if (status === "Present") row.style.background = "#eafaf1";
    else if (status === "Absent") row.style.background = "#fdecea";
    else if (status === "Late") row.style.background = "#fff6da";
}
