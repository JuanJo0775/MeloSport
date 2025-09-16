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
      try {
        return JSON.parse(str);
      } catch (e) {
        try {
          // eslint-disable-next-line no-new-func
          return new Function("return (" + str + ")")();
        } catch {
          return {};
        }
      }
    }

    function escapeHtml(str) {
      if (str === null || str === undefined) return "";
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
                        .replace(/'/g, "&#039;");
    }

    // ---------- configuración ----------
    const cfg = window.SALE_CONFIG || {};
    const prefix = cfg.prefix || "items";
    const SAVE_URL = cfg.SELECTION_SAVE_URL || window.SELECTION_SAVE_URL || '/backoffice/billing/selection/save/';

    const pageRoot = $qs("#sale-page");
    if (!pageRoot) return;

    // elementos
    const tableBody = $qs("#selected-products-table tbody", pageRoot);
    const totalDisplay = $qs("#total-display", pageRoot);
    const discountInput = $qs("#id_discount_percentage", pageRoot);
    const depositDisplay = $qs("#deposit-display", pageRoot);
    const paidInput = $qs("#id_amount_paid", pageRoot);
    const remainingDisplay = $qs("#remaining-display", pageRoot);

    const saleForm = $qs("#sale-form", pageRoot);
    const itemsFormsContainer = $qs("#items-forms-container", pageRoot);
    const emptyTemplateTextarea = $qs("#empty-item-template", pageRoot);
    const totalFormsEl = $qs(`#id_${prefix}-TOTAL_FORMS`, pageRoot);

    let previewMap = new Map();
    let firstCalc = true; // para establecer pago por defecto sólo la primera vez

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
      const productEl = itemsFormsContainer.querySelector(`[name="${base}-product"]`);
      const variantEl = itemsFormsContainer.querySelector(`[name="${base}-variant"]`);
      const qtyEl = itemsFormsContainer.querySelector(`[name="${base}-quantity"]`);
      const unitEl = itemsFormsContainer.querySelector(`[name="${base}-unit_price"]`);

      if (productEl) productEl.value = row.product_id;
      if (variantEl) variantEl.value = row.variant_id || "";
      if (qtyEl) qtyEl.value = row.qty;
      if (unitEl) unitEl.value = String(row.unit_price);

      // campos ocultos opcionales para debugging
      const hiddenSkuName = `${base}-variant_sku`;
      const hiddenLabelName = `${base}-variant_label`;
      if (!itemsFormsContainer.querySelector(`[name="${hiddenSkuName}"]`)) {
        const h1 = document.createElement('input');
        h1.type = 'hidden';
        h1.name = hiddenSkuName;
        h1.value = row.variant_id ? (row.sku || "") : "";
        itemsFormsContainer.appendChild(h1);
      }
      if (!itemsFormsContainer.querySelector(`[name="${hiddenLabelName}"]`)) {
        const h2 = document.createElement('input');
        h2.type = 'hidden';
        h2.name = hiddenLabelName;
        h2.value = row.variant_label || "";
        itemsFormsContainer.appendChild(h2);
      }
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

      const qtyInput = tr.querySelector(".preview-qty");
      qtyInput.addEventListener("input", e => {
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
      let subtotal = 0;
      previewMap.forEach(r => { subtotal += r.unit_price * r.qty; });

      const discountPct = parsePrice(discountInput?.value || 0);
      const discount = Math.round(subtotal * (discountPct / 100));

      let deposit = 0;
      try {
        deposit = parsePrice(depositDisplay?.dataset?.value ?? cfg.reservationDeposit ?? 0);
      } catch { deposit = 0; }

      const totalAfterDiscount = Math.max(0, subtotal - discount);

      if ((paidInput && String(paidInput.value || "").trim() === "") && firstCalc) {
        const defaultPaid = Math.max(0, totalAfterDiscount - deposit);
        if (paidInput) paidInput.value = defaultPaid;
      }
      firstCalc = false;

      const paid = parsePrice(paidInput?.value || 0);
      const remaining = Math.max(0, totalAfterDiscount - deposit - paid);

      $qs("#subtotal-display", pageRoot).textContent = fmtCOP(subtotal);
      $qs("#discount-display", pageRoot).textContent = fmtCOP(discount);
      depositDisplay.textContent = fmtCOP(deposit);
      $qs("#paid-display", pageRoot).textContent = fmtCOP(paid);
      remainingDisplay.textContent = fmtCOP(remaining);

      if (totalDisplay) totalDisplay.textContent = fmtCOP(totalAfterDiscount);

      toggleNoProductsRow();
    }

    // ---------- añadir item ----------
    function addItem(productObj, variantObj, qty) {
      const key = variantObj ? `${productObj.id}::${variantObj.id}` : `p::${productObj.id}`;
      qty = Math.max(1, Math.floor(Number(qty) || 1));

      if (previewMap.has(key)) {
        const row = previewMap.get(key);
        row.qty = row.qty + qty;
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
          formIndex: formIndex
        };

        insertFormsetForm(row);
        insertPreviewRow(row);
        previewMap.set(key, row);
      }

      recalcTotals();
    }

    // ---------- eventos ----------
    function attachAddButtons() {
      pageRoot.querySelectorAll(".btn-add-simple").forEach(btn => {
        btn.addEventListener("click", e => {
          e.preventDefault();
          const product = safeParseJSON(btn.getAttribute("data-product"));
          const qtyInput = btn.closest(".d-flex")?.querySelector(".simple-qty");
          const qty = Math.max(1, Math.floor(Number(qtyInput?.value || 1)));
          if (product && typeof product.stock !== "undefined" && qty > Number(product.stock || 0)) {
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
          if (variant && typeof variant.stock !== "undefined" && qty > Number(variant.stock || 0)) {
            alert(`Stock disponible: ${variant.stock}`);
            return;
          }
          addItem(product, variant, qty);
        });
      });
    }

    // Validación simple al enviar
    saleForm?.addEventListener("submit", e => {
      if (previewMap.size === 0) {
        e.preventDefault();
        alert("Debe agregar al menos un producto.");
      }
    });

    paidInput?.addEventListener("input", recalcTotals);
    discountInput?.addEventListener("input", recalcTotals);

    // ---------- init ----------
    attachAddButtons();
    function loadInitialItems() {
      const items = (cfg && cfg.reservationItems) || [];
      items.forEach(() => increaseTotalForms());
      items.forEach((it, idx) => {
        const row = {
          key: it.variant_id ? `${it.product_id}::${it.variant_id}` : `p::${it.product_id}`,
          product_id: it.product_id,
          product_name: it.product_name || "Producto",
          sku: it.sku || "",
          variant_id: it.variant_id || "",
          variant_label: it.variant_label || "",
          unit_price: parsePrice(it.unit_price),
          qty: parseInt(it.qty || "1"),
          formIndex: idx,
        };
        insertFormsetForm(row);
        insertPreviewRow(row);
        previewMap.set(row.key, row);
      });
      recalcTotals();
      toggleNoProductsRow();
    }
    loadInitialItems();
    recalcTotals();

    // ---------- guardar selección en sesión antes de filtrar/paginar (con AJAX parcial) ----------
    (function attachSelectionSaver() {
      if (!pageRoot) return;

      function getCSRFToken() {
        const m = document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)');
        return m ? m.pop() : '';
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

      function postSelection(items, deposit) {
        return fetch(SAVE_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
          },
          body: JSON.stringify({ items: items, deposit: deposit }),
          keepalive: true
        }).then(r => r.json()).catch(() => ({ ok: false }));
      }

      const filterForm = pageRoot.querySelector('form[method="get"]');
      if (filterForm) {
        filterForm.addEventListener('submit', function (e) {
          e.preventDefault();
          const url = (filterForm.action || window.location.pathname) + '?' +
                      (new URLSearchParams(new FormData(filterForm))).toString();
          const items = collectPreviewItems();
          const deposit = parsePrice(depositDisplay?.dataset?.value ?? cfg.reservationDeposit ?? 0);
          postSelection(items, deposit).then(() => {
            fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
              .then(resp => resp.text())
              .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newContainer = doc.querySelector('#products-container');
                const curContainer = document.querySelector('#products-container');
                if (newContainer && curContainer) {
                  curContainer.innerHTML = newContainer.innerHTML;
                  attachAddButtons();
                  attachPaginationLinks();
                } else {
                  window.location.href = url;
                }
              }).catch(() => { window.location.href = url; });
          });
        });
      }

      function attachPaginationLinks() {
        document.querySelectorAll('.pagination .page-link').forEach(a => {
          a.replaceWith(a.cloneNode(true));
        });
        document.querySelectorAll('.pagination .page-link').forEach(a => {
          a.addEventListener('click', function (ev) {
            ev.preventDefault();
            const url = a.href;
            const items = collectPreviewItems();
            const deposit = parsePrice(depositDisplay?.dataset?.value ?? cfg.reservationDeposit ?? 0);
            postSelection(items, deposit).then(() => {
              fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(resp => resp.text())
                .then(html => {
                  const parser = new DOMParser();
                  const doc = parser.parseFromString(html, 'text/html');
                  const newContainer = doc.querySelector('#products-container');
                  const curContainer = document.querySelector('#products-container');
                  if (newContainer && curContainer) {
                    curContainer.innerHTML = newContainer.innerHTML;
                    attachAddButtons();
                    attachPaginationLinks();
                  } else {
                    window.location.href = url;
                  }
                }).catch(() => { window.location.href = url; });
            });
          });
        });
      }

      attachPaginationLinks();
    })();

  })();
});
