(function () {
    const form = document.getElementById("jobSearch");
    const overlay = document.getElementById("jobSearchLoading");
    const list = document.getElementById("jobSearchLoadingList");
    if (!form || !overlay || !list) return;

    const labels = { naukri: "Naukri", linkedin: "LinkedIn" };

    form.addEventListener("submit", function () {
        const selected = Array.from(form.querySelectorAll('input[name="provider"]:checked')).map(function (box) {
            return labels[box.value] || "jobs";
        });
        const names = selected.length ? selected : ["jobs"];
        list.replaceChildren();
        names.forEach(function (name) {
            const row = document.createElement("div");
            row.className = "job-loading-row";
            const spinner = document.createElement("span");
            spinner.className = "job-loading-spinner";
            spinner.setAttribute("aria-hidden", "true");
            const label = document.createElement("span");
            label.className = "job-loading-label";
            label.textContent = "Loading " + name + "…";
            row.append(spinner, label);
            list.append(row);
        });
        overlay.classList.add("show");
        overlay.setAttribute("aria-busy", "true");
    });

    window.addEventListener("pageshow", function () {
        overlay.classList.remove("show");
        overlay.setAttribute("aria-busy", "false");
    });
})();

(function () {
    const PAGE_SIZE = 5;
    const results = document.getElementById("jobResults");
    const pager = document.getElementById("jobPager");
    if (!results || !pager) return;

    const rows = Array.from(results.querySelectorAll("tr.job-result"));
    const boards = Array.from(results.querySelectorAll("section.job-board"));
    const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    let page = 1;

    function chevron(direction) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("aria-hidden", "true");
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", direction === "prev" ? "M14.5 6L8.5 12L14.5 18" : "M9.5 6L15.5 12L9.5 18");
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", "currentColor");
        path.setAttribute("stroke-width", "2");
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        svg.appendChild(path);
        return svg;
    }

    function updateMoreLinks() {
        results.querySelectorAll(".job-description-wrap").forEach(function (wrap) {
            const text = wrap.querySelector(".job-description");
            const more = wrap.querySelector(".job-more");
            const row = wrap.closest("tr");
            if (!text || !more || (row && row.hidden)) return;
            if (text.classList.contains("is-open")) {
                more.hidden = false;
                return;
            }
            text.classList.add("is-clamped");
            more.hidden = text.scrollHeight <= text.clientHeight + 2;
        });
    }

    function renderPager() {
        if (!rows.length) {
            pager.hidden = true;
            return;
        }
        pager.hidden = false;
        pager.replaceChildren();

        const prev = document.createElement("button");
        prev.type = "button";
        prev.className = "job-page-icon";
        prev.setAttribute("aria-label", "Previous page");
        prev.disabled = page <= 1;
        prev.appendChild(chevron("prev"));
        prev.addEventListener("click", function () { showPage(page - 1, true); });

        const pages = document.createElement("div");
        pages.className = "job-pager-pages";
        for (let number = 1; number <= pageCount; number += 1) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "job-page" + (number === page ? " is-current" : "");
            button.textContent = String(number);
            button.setAttribute("aria-label", "Page " + number);
            if (number === page) button.setAttribute("aria-current", "page");
            button.addEventListener("click", function () { showPage(number, true); });
            pages.appendChild(button);
        }

        const next = document.createElement("button");
        next.type = "button";
        next.className = "job-page-icon";
        next.setAttribute("aria-label", "Next page");
        next.disabled = page >= pageCount;
        next.appendChild(chevron("next"));
        next.addEventListener("click", function () { showPage(page + 1, true); });

        pager.append(prev, pages, next);
    }

    function showPage(nextPage, scroll) {
        page = Math.min(Math.max(1, nextPage), pageCount);
        rows.forEach(function (row, index) {
            const start = (page - 1) * PAGE_SIZE;
            row.hidden = index < start || index >= start + PAGE_SIZE;
        });
        boards.forEach(function (board) {
            const visibleJob = board.querySelector("tr.job-result:not([hidden])");
            const hasJobs = board.querySelector("tr.job-result");
            board.hidden = Boolean(hasJobs) && !visibleJob;
        });
        renderPager();
        window.requestAnimationFrame(updateMoreLinks);
        if (scroll) results.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    results.addEventListener("click", function (event) {
        const more = event.target.closest(".job-more");
        if (!more || !results.contains(more)) return;
        const text = more.parentElement.querySelector(".job-description");
        if (!text) return;
        const open = text.classList.toggle("is-open");
        text.classList.toggle("is-clamped", !open);
        more.textContent = open ? "less" : "more";
    });

    showPage(1, false);
})();

(function () {
    const input = document.getElementById("resumeFile");
    const form = document.getElementById("resumeUpload");
    const status = document.getElementById("resumeStatus");
    if (!input || !form) return;
    input.addEventListener("change", function () {
        if (!input.files || !input.files.length) return;
        if (status) status.textContent = "Uploading " + input.files[0].name + "…";
        form.submit();
    });
})();

(function () {
    document.querySelectorAll(".apply-direct.is-unavailable").forEach(function (button) {
        button.addEventListener("click", function () {
            const company = button.getAttribute("data-company") || "this company";
            let note = button.parentElement.querySelector(".apply-note");
            if (!note) {
                note = document.createElement("p");
                note.className = "apply-note";
                button.insertAdjacentElement("afterend", note);
            }
            note.textContent = "No career page is listed for " + company + ".";
        });
    });
})();
