(function () {
    const form = document.getElementById("reviewForm");
    if (!form) return;

    const role = form.dataset.role;
    const action = form.dataset.action;
    const submit = document.getElementById("reviewSubmit");
    const missing = document.getElementById("missingNote");
    const oldValues = JSON.parse(form.dataset.oldValues || "{}");
    const oldNode = document.getElementById("oldValue");
    const fieldSelect = form.querySelector("[name=field]");

    function textValue(name) {
        const node = form.querySelector("[name=" + name + "]");
        return node ? node.value.trim() : "";
    }

    function checked(name) {
        const node = form.querySelector("[name=" + name + "]");
        return !!(node && node.checked);
    }

    function gaps() {
        const items = [];
        if (action === "approve" && role === "candidate") {
            if (!checked("confirm")) items.push("Accuracy confirmation");
            if (!textValue("target_role")) items.push("Target role");
            if (!checked("share_notice")) items.push("Share notice");
        } else if (action === "approve" && role === "hiring_manager") {
            if (!checked("confirm")) items.push("Resume review confirmation");
            if (!textValue("stage")) items.push("Next stage");
            if (!textValue("note")) items.push("Decision note");
        } else if (action === "approve" && role === "auditor") {
            if (!checked("confirm")) items.push("Record-complete confirmation");
            if (!textValue("note")) items.push("What was checked");
            if (!textValue("notice")) items.push("Candidate notice");
        } else if (action === "reject") {
            if (!textValue("reason_code")) items.push("Reason code");
            if (!textValue("note")) items.push("Written note");
            if (!textValue("next_step")) items.push("What happens next");
            if (!checked("confirm")) items.push("Confirmation");
            if (role !== "candidate" && !textValue("notice")) items.push("Candidate notice");
        } else if (action === "edit") {
            if (!textValue("field")) items.push(role === "auditor" ? "Field to annotate" : "Field to correct");
            if (!textValue("new_value")) items.push(role === "auditor" ? "Annotation" : "New value");
            if (role === "auditor" && !textValue("reason_code")) items.push("Annotation type");
            if (!textValue("note")) items.push("Reason");
        }
        return items;
    }

    function refresh() {
        if (fieldSelect && oldNode) {
            const key = fieldSelect.value;
            oldNode.textContent = key ? (oldValues[key] || "Empty") : "Select a field to show the current value";
        }
        const items = gaps();
        submit.disabled = items.length > 0;
        missing.textContent = items.length
            ? "Still required: " + items.join(", ")
            : "Required fields are filled.";
    }

    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);
    refresh();
})();
