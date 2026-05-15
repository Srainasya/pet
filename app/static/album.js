const dateInput = document.getElementById("dateInput");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const grid = document.getElementById("grid");
const statusEl = document.getElementById("status");

function todayISO() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

async function loadPhotos() {
  const date = dateInput.value || todayISO();
  statusEl.textContent = "載入中…";
  const r = await fetch(`/api/photos?date=${encodeURIComponent(date)}`);
  const j = await r.json();
  if (!r.ok) {
    statusEl.textContent = `載入失敗: ${j.error || r.status}`;
    return;
  }

  grid.innerHTML = "";
  j.items.forEach(item => {
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <img src="${item.url}" />
      <div class="muted">${item.created_at}</div>
    `;
    grid.appendChild(div);
  });

  statusEl.textContent = `共 ${j.items.length} 張`;
}

async function uploadPhoto() {
  const f = fileInput.files[0];
  if (!f) {
    statusEl.textContent = "請先選一張照片";
    return;
  }

  const date = dateInput.value || todayISO();
  const fd = new FormData();
  fd.append("file", f);
  fd.append("date", date);

  statusEl.textContent = "上傳中…";
  const r = await fetch("/api/photos/upload", { method: "POST", body: fd });
  const j = await r.json();
  if (!r.ok) {
    statusEl.textContent = `上傳失敗: ${j.error || r.status}`;
    return;
  }

  fileInput.value = "";
  await loadPhotos();
  statusEl.textContent = "上傳完成 🎉 +5 coins！";
}

dateInput.value = todayISO();
dateInput.addEventListener("change", loadPhotos);
uploadBtn.addEventListener("click", uploadPhoto);

loadPhotos();