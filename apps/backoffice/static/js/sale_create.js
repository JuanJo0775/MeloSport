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

    const pageRoot = $qs("#sale-page");
    if (!pageRoot) return;

    const tableBody = $qs("#selected-products-table tbody", pageRoot);
    const totalDisplay = $qs("#total-display", pageRoot);
    const discountInput = $qs("#id_discount_percentage", pageRoot); // porcentaje
    const depositDisplay = $qs("#deposit-display", pageRoot);
    const paidInput = $qs("#id_amount_paid", pageRoot);
    const remainingDisplay = $qs("#remaining-display", pageRoot);

    const saleForm = $qs("#sale-form", pageRoot);
    const itemsFormsContainer = $qs("#items-forms-container", pageRoot);
    const emptyTemplateTextarea = $qs("#empty-item-template", pageRoot);
    const totalFormsEl = $qs(`#id_${prefix}-TOTAL_FORMS`, pageRoot);

    let previewMap = new Map();

    function getNextFormIndex() { return Number(totalFormsEl?.value || 0); }
    function increaseTotalForms() {
      const val = getNextFormIndex() + 1;
      if (totalFormsEl) totalFormsEl.value = String(val);
      // retornamos el índice disponible (val - 1)
      return val - 1;
    }
    function decreaseTotalForms() {
      if (totalFormsEl) totalFormsEl.value = String(Math.max(0, getNextFormIndex() - 1));
    }

    // ---------- utilidades de UI: placeholder y numeración ----------
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
      // siempre actualizar numeración cuando cambia el estado
      updateRowNumbers();
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
          variant_label: variantObj ? variantObj.label : "",
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

    // ---------- formset ----------
    function insertFormsetForm(row) {
      const tpl = emptyTemplateTextarea?.value || "";
      if (!tpl) {
        console.error("❌ No se encontró plantilla de formset vacío");
        return;
      }

      const html = tpl
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#039;/g, "'");
      const newForm = html.replace(/__prefix__/g, row.formIndex);

      itemsFormsContainer.insertAdjacentHTML("beforeend", newForm);

      const base = `${prefix}-${row.formIndex}`;
      const prodEl = itemsFormsContainer.querySelector(`[name="${base}-product"]`);
      const variantEl = itemsFormsContainer.querySelector(`[name="${base}-variant"]`);
      const qtyEl = itemsFormsContainer.querySelector(`[name="${base}-quantity"]`);
      const upEl = itemsFormsContainer.querySelector(`[name="${base}-unit_price"]`);

      if (prodEl) {
        prodEl.value = String(row.product_id);
        prodEl.dataset.name = row.product_name || "Producto";
        prodEl.dataset.sku = row.sku || "";
      }
      if (variantEl) {
        variantEl.value = row.variant_id || "";
        if (row.variant_label) variantEl.dataset.label = row.variant_label;
      }
      if (qtyEl) qtyEl.value = String(row.qty);
      if (upEl) upEl.value = String(row.unit_price);

      console.log(`✅ Formset insertado en índice ${row.formIndex}`, {
        prodEl, variantEl, qtyEl, upEl,
      });
    }

    // ---------- tabla ----------
    function insertPreviewRow(row) {
      const tr = document.createElement("tr");
      tr.dataset.key = row.key;
      tr.classList.add("product-row");
      tr.innerHTML = `
        <td class="text-muted small align-middle">#</td>
        <td>
          <div class="fw-semibold text-dark small">${escapeHtml(row.product_name)}</div>
          ${row.variant_label 
            ? `<div class="text-muted small">Variante: <span class="fw-medium">${escapeHtml(row.variant_label)}</span></div>` 
            : ""}
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
          <button class="btn btn-sm btn-outline-danger btn-remove-item" type="button"
                  title="Quitar producto">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      `;
      // append al tbody (si existe placeholder, seguirá ahí pero oculto cuando haya productos)
      tableBody.appendChild(tr);

      // eventos de cantidad
      const qtyInput = tr.querySelector(".preview-qty");
      qtyInput.addEventListener("input", e => {
        const v = Math.max(1, Math.floor(Number(e.target.value || 1)));
        row.qty = v;
        updateFormQuantity(row.formIndex, v);
        tr.querySelector(".subtotal").textContent = fmtCOP(row.unit_price * v);
        recalcTotals();
      });

      // evento eliminar
      tr.querySelector(".btn-remove-item").addEventListener("click", () => {
        previewMap.delete(row.key);
        tr.remove();
        decreaseTotalForms();
        recalcTotals();
        toggleNoProductsRow();  // asegurar actualización del placeholder y numeración
      });

      toggleNoProductsRow();  // esconder placeholder y renumerar
    }

    function updatePreviewRow(row) {
      const tr = tableBody.querySelector(`tr[data-key="${row.key}"]`);
      if (!tr) return;
      const qtyInput = tr.querySelector(".preview-qty");
      if (qtyInput) qtyInput.value = row.qty;
      const subtotalEl = tr.querySelector(".subtotal");
      if (subtotalEl) subtotalEl.textContent = fmtCOP(row.unit_price * row.qty);
      // renumerar por si algo cambió
      updateRowNumbers();
    }

    function updateFormQuantity(index, qty) {
      const el = itemsFormsContainer.querySelector(`[name="${prefix}-${index}-quantity"]`);
      if (el) el.value = qty;
    }

    // ---------- cargar items iniciales (reserva) ----------
    function loadInitialItems() {
      const items = (window.SALE_CONFIG && window.SALE_CONFIG.reservationItems) || [];
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

      if (totalFormsEl) {
        totalFormsEl.value = String(items.length);
      }

      recalcTotals();
      toggleNoProductsRow(); // asegura el estado inicial
    }

        // ---------- totales extendidos ----------
    function recalcTotals() {
      let subtotal = 0;
      previewMap.forEach(r => { subtotal += r.unit_price * r.qty; });

      const discountPct = parsePrice(discountInput?.value || 0);
      const discount = Math.round(subtotal * (discountPct / 100));
      const deposit = parsePrice(depositDisplay?.dataset.value || 0);

      const totalAfterDiscount = Math.max(0, subtotal - discount);

      // forzar siempre el valor del campo de pago al saldo pendiente neto de depósito
      paidInput.value = totalAfterDiscount - deposit;
      const paid = parsePrice(paidInput.value || 0);

      const remaining = Math.max(0, totalAfterDiscount - deposit - paid);

      // actualizar spans
      $qs("#subtotal-display", pageRoot).textContent = fmtCOP(subtotal);
      $qs("#discount-display", pageRoot).textContent = fmtCOP(discount);
      depositDisplay.textContent = fmtCOP(deposit);
      $qs("#paid-display", pageRoot).textContent = fmtCOP(paid);
      remainingDisplay.textContent = fmtCOP(remaining);

      // mantener total principal en el footer de la tabla
      if (totalDisplay) totalDisplay.textContent = fmtCOP(totalAfterDiscount);

      // actualizar placeholder / numeración
      toggleNoProductsRow();
    }

    // ---------- eventos: añadir botones ----------
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

    // ---------- validación del pago ----------
    function getSelectedPaymentMethod() {
      const els = pageRoot.querySelectorAll('[name="payment_method"]');
      if (!els || els.length === 0) return null;
      for (let i = 0; i < els.length; i++) {
        if (els[i].checked) return els[i].value;
      }
      return null;
    }

    function togglePaymentProviderVisibility() {
      const pm = getSelectedPaymentMethod();
      const providerGroup = $qs("#payment-provider-group", pageRoot);
      if (!providerGroup) return;
      if (pm === "DI") {
        providerGroup.style.display = "";
      } else {
        providerGroup.style.display = "none";
        const sel = providerGroup.querySelector('select, input');
        if (sel) sel.value = "";
      }
    }

    function validateBeforeSubmit(e) {
      if (previewMap.size === 0) {
        e.preventDefault();
        alert("Debe agregar al menos un producto.");
        return false;
      }
      const pm = getSelectedPaymentMethod();
      if (pm === "DI") {
        const prov = pageRoot.querySelector('[name="payment_provider"]');
        if (!prov || !prov.value) {
          e.preventDefault();
          alert("Debes seleccionar el proveedor (Nequi / Daviplata).");
          return false;
        }
      }
      const remainingText = remainingDisplay?.textContent || "";
      if (remainingText.startsWith("-")) {
        e.preventDefault();
        alert("El saldo restante no puede ser negativo.");
        return false;
      }
      return true;
    }

    // ---------- attach ----------
    function attachPaymentListeners() {
      const pmEls = pageRoot.querySelectorAll('[name="payment_method"]');
      pmEls.forEach(el => el.addEventListener("change", togglePaymentProviderVisibility));
      togglePaymentProviderVisibility();
    }

    discountInput?.addEventListener("input", recalcTotals);

    // quitamos el listener manual de amount_paid porque ahora es automático
    // paidInput?.addEventListener("input", recalcTotals);

    // ---------- submit ----------
    saleForm?.addEventListener("submit", e => {
      console.log("TOTAL_FORMS al enviar:", totalFormsEl?.value);  // 👈 Debug (puedes eliminar)
      if (!validateBeforeSubmit(e)) return;
    });

    // ---------- init ----------
    attachAddButtons();
    attachPaymentListeners();
    loadInitialItems();
    recalcTotals();

    // ---------- guardar selección en sesión antes de filtrar/paginar ----------
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

      const SAVE_URL = window.SELECTION_SAVE_URL || '/backoffice/billing/selection/save/';

      function saveSelectionThenNavigate(targetUrl) {
        const items = collectPreviewItems();
        fetch(SAVE_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
          },
          body: JSON.stringify({ items: items }),
          keepalive: true
        }).catch(() => {
          // si falla no bloqueamos la navegación
        }).finally(() => {
          if (targetUrl) window.location.href = targetUrl;
        });
      }

      // interceptar envíos GET de filtros (form de búsqueda)
      const filterForm = pageRoot.querySelector('form[method="get"]');
      if (filterForm) {
        filterForm.addEventListener('submit', function (e) {
          e.preventDefault();
          const url = (filterForm.action || window.location.pathname) + '?' +
                      (new URLSearchParams(new FormData(filterForm))).toString();
          saveSelectionThenNavigate(url);
        });
      }

      // interceptar clicks en paginación
      pageRoot.querySelectorAll('.pagination .page-link').forEach(a => {
        a.addEventListener('click', function (ev) {
          ev.preventDefault();
          saveSelectionThenNavigate(a.href);
        });
      });
    })();

  })();
});

