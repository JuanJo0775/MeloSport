/* static/js/reservation_create.js
 * Funcionalidad completa:
 * - carga productos con filtros y paginación (Página 1, 2, ...)
 * - render tarjetas con variantes
 * - agrega productos al formset
 * - preview en tabla
 * - totales, abono mínimo, días 3/30
 * - eliminación simple (sin modal)
 */

document.addEventListener("DOMContentLoaded", function () {
  (function () {
    // helpers
    function $qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function fmtCOP(n) {
      if (n === null || n === undefined || n === "") return "$ 0";
      const num = Number(n) || 0;
      return "$ " + Math.round(num).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    }
    function parseNumberSafe(s) { return Number(String(s).replace(/\./g, "").replace(/,/g, ".")) || 0; }
    function escapeHtml(str) {
      if (!str && str !== 0) return "";
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // config desde template
    const cfg = window.RESERVATION_CONFIG || {};
    const productsApi = cfg.productsApiUrl || "/billing/products/json/";
    const prefix = cfg.prefix || "items";

    // elementos
    const productsContainer = $qs("#products-container");
    const paginationContainer = $qs("#pagination-container");
    const searchInput = $qs("#product-search");
    const typeFilter = $qs("#product-type-filter");
    const inStockOnly = $qs("#in-stock-only");
    const toggleProductsBtn = $qs("#toggle-products-panel-btn");

    const tableBody = $qs("#selected-products-table tbody");
    const totalDisplay = $qs("#total-display");
    const minDepositDisplay = $qs("#min-deposit-display");
    const dueMessage = $qs("#due-message");
    const amountDepositedInput = $qs("#id_amount_deposited");
    const reservationForm = $qs("#reservation-form");
    const itemsFormsContainer = $qs("#items-forms-container");
    const emptyTemplateTextarea = $qs("#empty-item-template");

    const totalFormsEl = $qs(`#id_${prefix}-TOTAL_FORMS`);
    let previewMap = new Map();

    // cargar productos
    async function loadProducts(page = 1) {
      productsContainer.innerHTML = `<div class="text-center p-3"><div class="spinner-border"></div></div>`;
      if (paginationContainer) paginationContainer.innerHTML = "";

      const params = new URLSearchParams();
      if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
      if (typeFilter.value) params.set("type", typeFilter.value);
      if (inStockOnly.checked) params.set("stock", "in_stock");
      params.set("page", page);

      try {
        const resp = await fetch(productsApi + "?" + params.toString());
        const data = await resp.json();
        renderProducts(data.products || []);
        renderPagination(data.page, data.num_pages);
      } catch {
        productsContainer.innerHTML = `<div class="text-danger">Error cargando productos</div>`;
      }
    }

    function renderProducts(products) {
      productsContainer.innerHTML = "";
      if (!products.length) {
        productsContainer.innerHTML = `<div class="text-muted text-center">No se encontraron productos.</div>`;
        return;
      }
      products.forEach(p => {
        const card = document.createElement("div");
        card.className = "card mb-2";
        const hasVariants = p.variants && p.variants.length > 0;
        const img = p.image ? `<img src="${p.image}" style="width:72px;height:72px;object-fit:cover;" class="me-2">` : "";

        card.innerHTML = `
          <div class="card-body">
            <div class="d-flex">
              ${img}
              <div style="flex:1">
                <div><strong>${escapeHtml(p.name)}</strong></div>
                <div class="text-muted">SKU: ${escapeHtml(p.sku || "-")}</div>
                <div class="text-muted">Stock: ${p.stock ?? "-"}</div>
                <div>Precio: <strong>${fmtCOP(p.price)}</strong></div>
                <div data-variants-area></div>
              </div>
              <div class="text-end">
                <input type="number" min="1" value="1" class="form-control form-control-sm mb-2 quantity-input" style="width:80px">
                <button class="btn btn-sm btn-primary add-product-btn">Agregar</button>
              </div>
            </div>
          </div>
        `;

        const variantsArea = card.querySelector("[data-variants-area]");
        if (hasVariants) {
          const sel = document.createElement("select");
          sel.className = "form-select form-select-sm mb-2 variant-select";
          sel.innerHTML = `<option value="">-- Seleccione variante --</option>`;
          p.variants.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.id;
            opt.textContent = `${v.label}${v.stock ? " (stock: " + v.stock + ")" : ""}`;
            opt.dataset.stock = v.stock || "";
            opt.dataset.price = v.price || p.price || 0;
            sel.appendChild(opt);
          });
          variantsArea.appendChild(sel);
        }

        const addBtn = card.querySelector(".add-product-btn");
        const qtyInput = card.querySelector(".quantity-input");
        const variantSelect = card.querySelector(".variant-select");

        addBtn.addEventListener("click", () => {
          const qty = Number(qtyInput.value) || 1;
          let variantId = null;
          let unitPrice = p.price || 0;
          let stock = p.stock ?? Infinity;
          let variantLabel = "";

          if (variantSelect) {
            const opt = variantSelect.selectedOptions[0];
            if (!opt.value) return alert("Seleccione una variante");
            variantId = opt.value;
            unitPrice = Number(opt.dataset.price);
            stock = Number(opt.dataset.stock);
            variantLabel = opt.textContent;
          }
          if (qty > stock) return alert("Cantidad supera el stock");

          addProductToFormset({
            product_id: p.id,
            product_name: p.name,
            sku: p.sku || "",
            image: p.image || "",
            variant_id: variantId,
            variant_label: variantLabel,
            quantity: qty,
            unit_price: unitPrice,
            subtotal: qty * unitPrice
          });
        });

        productsContainer.appendChild(card);
      });
    }

    function renderPagination(page, numPages) {
      if (!paginationContainer || !numPages) return;
      let html = "";
      for (let i = 1; i <= numPages; i++) {
        html += `<li class="page-item ${i === page ? "active" : ""}">
          <button class="page-link" data-page="${i}">${i}</button>
        </li>`;
      }
      paginationContainer.innerHTML = html;
      paginationContainer.querySelectorAll("button").forEach(btn => {
        btn.addEventListener("click", () => loadProducts(Number(btn.dataset.page)));
      });
    }

    function addProductToFormset(opts) {
      let idx = parseInt(totalFormsEl.value, 10);
      const tpl = emptyTemplateTextarea.value.replace(/__prefix__/g, idx);
      const wrapper = document.createElement("div");
      wrapper.className = "d-none";
      wrapper.dataset.formIndex = idx;
      wrapper.innerHTML = tpl;
      itemsFormsContainer.appendChild(wrapper);

      wrapper.querySelector(`[name="${prefix}-${idx}-product"]`).value = opts.product_id;
      wrapper.querySelector(`[name="${prefix}-${idx}-variant"]`).value = opts.variant_id || "";
      wrapper.querySelector(`[name="${prefix}-${idx}-quantity"]`).value = opts.quantity;
      wrapper.querySelector(`[name="${prefix}-${idx}-unit_price"]`).value = opts.unit_price;
      totalFormsEl.value = idx + 1;

      $qs("#no-products-row")?.remove();
      const row = document.createElement("tr");
      row.dataset.formIndex = idx;
      row.innerHTML = `
        <td><img src="${opts.image}" style="width:48px;height:48px;object-fit:cover;"></td>
        <td><strong>${escapeHtml(opts.product_name)}</strong><div class="small text-muted">${escapeHtml(opts.variant_label || opts.sku)}</div></td>
        <td>${opts.quantity}</td>
        <td>${fmtCOP(opts.unit_price)}</td>
        <td><span class="preview-subtotal">${fmtCOP(opts.subtotal)}</span></td>
        <td><button class="btn btn-sm btn-outline-danger remove-item-btn">✕</button></td>
      `;
      tableBody.appendChild(row);

      const deleteInput = wrapper.querySelector(`[name="${prefix}-${idx}-DELETE"]`);
      row.querySelector(".remove-item-btn").addEventListener("click", () => {
        if (deleteInput) deleteInput.checked = true;
        row.remove();
        previewMap.delete(String(idx));
        if (!previewMap.size) {
          tableBody.innerHTML = `<tr class="text-muted" id="no-products-row"><td colspan="6" class="text-center">No hay productos seleccionados.</td></tr>`;
        }
        recalcTotals();
      });

      previewMap.set(String(idx), row);
      recalcTotals();
    }

    function recalcTotals() {
      let total = 0;
      previewMap.forEach(row => {
        const subEl = row.querySelector(".preview-subtotal");
        if (subEl) total += parseNumberSafe(subEl.textContent);
      });
      totalDisplay.textContent = fmtCOP(total);
      const minDep = Math.round(total * 0.2);
      minDepositDisplay.textContent = fmtCOP(minDep);
      const abono = parseNumberSafe(amountDepositedInput.value);
      if (abono >= minDep && total > 0) {
        dueMessage.textContent = "Reserva válida por 30 días hábiles";
        dueMessage.className = "badge bg-success";
      } else {
        dueMessage.textContent = "Reserva válida por 3 días hábiles";
        dueMessage.className = "badge bg-info text-dark";
      }
    }

    reservationForm.addEventListener("submit", e => {
      if (!previewMap.size) {
        e.preventDefault();
        alert("Debe agregar al menos un producto.");
      }
    });

    searchInput.addEventListener("keydown", e => {
      if (e.key === "Enter") { e.preventDefault(); loadProducts(); }
    });
    searchInput.addEventListener("input", () => loadProducts());
    typeFilter.addEventListener("change", () => loadProducts());
    inStockOnly.addEventListener("change", () => loadProducts());

    toggleProductsBtn.addEventListener("click", () => {
      const panel = $qs("#products-panel");
      panel.style.display = panel.style.display === "none" ? "" : "none";
    });

    amountDepositedInput.addEventListener("input", recalcTotals);

    // primera carga
    loadProducts();
  })();
});
