document.addEventListener("DOMContentLoaded", function () {
  (function () {
    // ---------- helpers ----------
    function $qs(sel, ctx) { return (ctx || document).querySelector(sel); }

    function fmtCOP(n) {
      const num = Number(n) || 0;
      return "$ " + num.toLocaleString("es-CO");
    }

    function parsePrice(val) {
      if (val === null || val === undefined) return 0;
      if (typeof val === "number") return Math.round(val);
      let s = String(val).trim();
      s = s.replace(/\u00A0/g, "").replace(/\s/g, "")
           .replace(/\$/g, "").replace(/COP/ig, "");
      s = s.replace(/[^0-9\.,-]/g, "");
      if (!s) return 0;

      if (s.indexOf(".") !== -1 && s.indexOf(",") !== -1) {
        if (s.lastIndexOf(",") > s.lastIndexOf(".")) {
          s = s.replace(/\./g, "").replace(/,/g, ".");
        } else {
          s = s.replace(/,/g, "");
        }
      } else if (s.indexOf(",") !== -1) {
        const parts = s.split(",");
        if (parts.length > 1 && parts[1].length === 3) {
          s = s.replace(/,/g, "");
        } else {
          s = s.replace(/,/g, ".");
        }
      } else if (s.indexOf(".") !== -1) {
        const parts = s.split(".");
        if (parts.length > 1 && parts[1].length === 3) {
          s = s.replace(/\./g, "");
        }
      }

      const n = parseFloat(s);
      return isNaN(n) ? 0 : Math.round(n);
    }

    function safeParseJSON(str) {
      if (!str) return {};
      try { return JSON.parse(str); }
      catch { try { return new Function("return (" + str + ")")(); } catch { return {}; } }
    }

    function escapeHtml(str) {
      if (str === null || str === undefined) return "";
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
                        .replace(/'/g, "&#039;");
    }

    function getCSRFToken() {
      const m = document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)');
      return m ? m.pop() : '';
    }

    // ---------- configuración ----------
    const cfg = window.BILLING_SELECTION || window.RESERVATION_CONFIG || {};
    const prefix = cfg.prefix || "items";
    const SAVE_URL = cfg.saveUrl || '/backoffice/billing/selection/save/';

    const pageRoot = $qs("#reservation-page");
    if (!pageRoot) return;

    // elementos
    const tableBody = $qs("#selected-products-table tbody", pageRoot);
    const totalDisplay = $qs("#total-display", pageRoot);
    const minDepositDisplay = $qs("#min-deposit-display", pageRoot);
    const dueMessage = $qs("#due-message", pageRoot);
    const amountDepositedInput = $qs("#id_amount_deposited", pageRoot);
    const reservationForm = $qs("#reservation-form", pageRoot);
    const itemsFormsContainer = $qs("#items-forms-container", pageRoot);
    const emptyTemplateTextarea = $qs("#empty-item-template", pageRoot);
    const totalFormsEl = $qs(`#id_${prefix}-TOTAL_FORMS`, pageRoot);

    let previewMap = new Map();

    function getNextFormIndex() { return Number(totalFormsEl?.value || 0); }
    function increaseTotalForms() {
      const val = getNextFormIndex() + 1;
      if (totalFormsEl) totalFormsEl.value = String(val);
      return val - 1;
    }
    function decreaseTotalForms() {
      if (totalFormsEl) totalFormsEl.value = String(Math.max(0, getNextFormIndex() - 1));
    }

    // ---------- formset ----------
    function insertFormsetForm(row) {
      const tpl = emptyTemplateTextarea?.value || "";
      const html = tpl.replace(/&lt;/g, "<").replace(/&gt;/g, ">")
                      .replace(/&quot;/g, '"').replace(/&#039;/g, "'");
      const newForm = html.replace(/__prefix__/g, row.formIndex);
      itemsFormsContainer.insertAdjacentHTML("beforeend", newForm);

      const base = `${prefix}-${row.formIndex}`;
      itemsFormsContainer.querySelector(`[name="${base}-product"]`).value = row.product_id;
      itemsFormsContainer.querySelector(`[name="${base}-variant"]`).value = row.variant_id || "";
      itemsFormsContainer.querySelector(`[name="${base}-quantity"]`).value = row.qty;
      itemsFormsContainer.querySelector(`[name="${base}-unit_price"]`).value = String(row.unit_price);
    }

    // ---------- tabla ----------
    function updateRowNumbers() {
      const rows = tableBody.querySelectorAll("tr.product-row");
      rows.forEach((r, idx) => {
        const firstCell = r.querySelector("td");
        if (firstCell) firstCell.textContent = String(idx + 1);
      });
    }

    function toggleNoProductsRow() {
      const noRow = $qs("#no-products-row", pageRoot);
      if (!noRow) return;
      noRow.style.display = previewMap.size > 0 ? "none" : "";
      updateRowNumbers();
    }

    function insertPreviewRow(row) {
      const tr = document.createElement("tr");
      tr.dataset.key = row.key;
      tr.classList.add("product-row");
      tr.innerHTML = `
        <td class="text-muted small align-middle">#</td>
        <td>
          <div class="fw-semibold text-dark small">${escapeHtml(row.product_name)}</div>
          ${row.variant_label ? `<div class="text-muted small">Variante: <span class="fw-medium">${escapeHtml(row.variant_label)}</span></div>` : ""}
          <div class="text-muted text-mono small">SKU: ${escapeHtml(row.sku) || "-"}</div>
        </td>
        <td class="text-center align-middle">
          <input type="number" min="1" value="${row.qty}"
                 class="form-control form-control-sm text-center preview-qty"
                 style="width:75px;">
        </td>
        <td class="text-end align-middle unit-price fw-medium text-primary">
          ${fmtCOP(row.unit_price)}
        </td>
        <td class="text-end align-middle subtotal fw-bold text-success">
          ${fmtCOP(row.unit_price * row.qty)}
        </td>
        <td class="text-center align-middle">
          <button class="btn btn-sm btn-outline-danger btn-remove-item" type="button" title="Quitar producto">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      `;
      tableBody.appendChild(tr);

      tr.querySelector(".preview-qty").addEventListener("input", e => {
        const v = Math.max(1, Math.floor(Number(e.target.value || 1)));
        row.qty = v;
        updateFormQuantity(row.formIndex, v);
        tr.querySelector(".subtotal").textContent = fmtCOP(row.unit_price * v);
        recalcTotals();
      });

      tr.querySelector(".btn-remove-item").addEventListener("click", () => {
        previewMap.delete(row.key);
        tr.remove();
        decreaseTotalForms();
        recalcTotals();
        updateRowNumbers();
        toggleNoProductsRow();
      });

      updateRowNumbers();
      toggleNoProductsRow();
    }

    function updatePreviewRow(row) {
      const tr = tableBody.querySelector(`tr[data-key="${row.key}"]`);
      if (!tr) return;
      const qtyInput = tr.querySelector(".preview-qty");
      if (qtyInput) qtyInput.value = row.qty;
      const subtotalEl = tr.querySelector(".subtotal");
      if (subtotalEl) subtotalEl.textContent = fmtCOP(row.unit_price * row.qty);
      updateRowNumbers();
    }

    function updateFormQuantity(index, qty) {
      const el = itemsFormsContainer.querySelector(`[name="${prefix}-${index}-quantity"]`);
      if (el) el.value = qty;
    }

    // ---------- totales ----------
    function recalcTotals() {
      let total = 0;
      previewMap.forEach(r => { total += r.unit_price * r.qty; });

      totalDisplay.textContent = fmtCOP(total);

      const minDep = Math.round(total * 0.2);
      if (minDepositDisplay) minDepositDisplay.textContent = fmtCOP(minDep);

      const dep = parsePrice(amountDepositedInput?.value || cfg.deposit || 0);

      $qs("#subtotal-display", pageRoot).textContent = fmtCOP(total);
      $qs("#deposit-display", pageRoot).textContent = fmtCOP(dep);
      $qs("#remaining-display", pageRoot).textContent = fmtCOP(Math.max(0, total - dep));

      if (dueMessage) {
        dueMessage.textContent =
          total === 0
            ? "Seleccione productos para calcular vencimiento."
            : dep >= minDep
            ? "Reserva válida por 30 días."
            : "Reserva válida por 3 días (abono mínimo 20%).";
      }

      toggleNoProductsRow();
    }

    // ---------- añadir ----------
    function addItem(productObj, variantObj, qty) {
      const key = variantObj ? `${productObj.id}::${variantObj.id}` : `p::${productObj.id}`;
      qty = Math.max(1, Math.floor(Number(qty) || 1));

      if (previewMap.has(key)) {
        const row = previewMap.get(key);
        row.qty += qty;
        updatePreviewRow(row);
        updateFormQuantity(row.formIndex, row.qty);
      } else {
        const formIndex = increaseTotalForms();
        const rawPrice = variantObj ? variantObj.price : productObj.price;
        const unitPrice = parsePrice(rawPrice);

        const row = {
          key,
          product_id: productObj.id,
          product_name: productObj.name || productObj.label || "",
          sku: variantObj ? (variantObj.sku || "") : (productObj.sku || ""),
          variant_id: variantObj ? variantObj.id : "",
          variant_label: variantObj ? (variantObj.label || "") : "",
          unit_price: unitPrice,
          qty: qty,
          formIndex
        };
        insertFormsetForm(row);
        insertPreviewRow(row);
        previewMap.set(key, row);
      }

      recalcTotals();
    }

    function attachAddButtons() {
      pageRoot.querySelectorAll(".btn-add-simple").forEach(btn => {
        btn.addEventListener("click", e => {
          e.preventDefault();
          const product = safeParseJSON(btn.getAttribute("data-product"));
          const qtyInput = btn.closest(".d-flex")?.querySelector(".simple-qty");
          const qty = Math.max(1, Math.floor(Number(qtyInput?.value || 1)));
          if (product && qty > (Number(product.stock || 0))) {
            alert(`Stock disponible: ${product.stock}`);
            return;
          }
          addItem(product, null, qty);
        });
      });

      pageRoot.querySelectorAll(".btn-add-variant").forEach(btn => {
        btn.addEventListener("click", e => {
          e.preventDefault();
          const product = safeParseJSON(btn.getAttribute("data-product"));
          const variant = safeParseJSON(btn.getAttribute("data-variant"));
          const rowEl = btn.closest("tr");
          const qtyInput = rowEl?.querySelector(".variant-qty-input");
          const qty = Math.max(1, Math.floor(Number(qtyInput?.value || 1)));
          if (variant && qty > (Number(variant.stock || 0))) {
            alert(`Stock disponible: ${variant.stock}`);
            return;
          }
          addItem(product, variant, qty);
        });
      });
    }

    reservationForm?.addEventListener("submit", e => {
      if (previewMap.size === 0) {
        e.preventDefault();
        alert("Debe agregar al menos un producto.");
      }
    });

    amountDepositedInput?.addEventListener("input", recalcTotals);

    // ---------- init ----------
    attachAddButtons();
    recalcTotals();

    // ---------- persistencia en sesión ----------
    async function getDepositValue() {
      return parsePrice(amountDepositedInput?.value || cfg.deposit || 0);
    }

    function collectPreviewItems() {
      const arr = [];
      previewMap.forEach(r => {
        arr.push({
          product_id: r.product_id,
          variant_id: r.variant_id || null,
          qty: r.qty,
          unit_price: r.unit_price,
          product_name: r.product_name,
          sku: r.sku,
          variant_label: r.variant_label
        });
      });
      return arr;
    }

    async function saveSelection() {
      const items = collectPreviewItems();
      const deposit = await getDepositValue();
      try {
        const resp = await fetch(SAVE_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
          },
          body: JSON.stringify({ items: items, deposit: String(deposit) }),
          keepalive: true
        });
        const data = await resp.json().catch(()=>({ok:false}));
        return (resp.ok && data.ok) ? {ok:true,data} : {ok:false,data};
      } catch(err) {
        return {ok:false,error:err};
      }
    }

    async function saveThenNavigate(url, useAjax=true) {
      await saveSelection();
      if (useAjax) {
        try {
          const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
          const html = await resp.text();
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const newContainer = doc.querySelector('#products-container');
          const curContainer = document.querySelector('#products-container');
          if (newContainer && curContainer) {
            curContainer.innerHTML = newContainer.innerHTML;
            attachAddButtons();
            attachPaginationLinks();
            return;
          }
        } catch (e) {
          console.warn("AJAX falló, redirigiendo...", e);
        }
      }
      window.location.href = url;
    }

    const filterForm = pageRoot.querySelector('form[method="get"]');
    if (filterForm) {
      filterForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const url = (filterForm.action || window.location.pathname) + '?' +
                    (new URLSearchParams(new FormData(filterForm))).toString();
        saveThenNavigate(url, true);
      });
    }

    function attachPaginationLinks() {
      document.querySelectorAll('.pagination .page-link').forEach(a => {
        a.replaceWith(a.cloneNode(true));
      });
      document.querySelectorAll('.pagination .page-link').forEach(a => {
        a.addEventListener('click', function (ev) {
          ev.preventDefault();
          saveThenNavigate(a.href, true);
        });
      });
    }
    attachPaginationLinks();

  })();
});
