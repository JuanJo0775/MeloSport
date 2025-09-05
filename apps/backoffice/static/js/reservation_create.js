document.addEventListener("DOMContentLoaded", function () {
  (function () {
    function $qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function fmtCOP(n) {
      const num = parseFloat(n) || 0;
      return "$ " + num.toLocaleString("es-CO");
    }
    function parseNumberSafe(s) {
      return Number(String(s).replace(/\./g, "").replace(/,/g, ".")) || 0;
    }
    function escapeHtml(str) {
      if (!str) return "";
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    const cfg = window.RESERVATION_CONFIG || {};
    const productsApi = cfg.productsApiUrl || "/billing/products/json/";
    const prefix = cfg.prefix || "items";

    const pageRoot = $qs("#reservation-page");
    if (!pageRoot) return;

    const productsContainer = $qs("#products-container", pageRoot);
    const paginationContainer = $qs("#pagination-container", pageRoot);
    const searchInput = $qs("#product-search", pageRoot);
    const clearSearchBtn = $qs("#clear-search", pageRoot);
    const typeFilter = $qs("#product-type-filter", pageRoot); // select con all/simple/variants
    const inStockOnly = $qs("#in-stock-only", pageRoot);

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

    function getNextFormIndex() { return Number(totalFormsEl.value || "0"); }
    function increaseTotalForms() {
      const val = getNextFormIndex() + 1;
      totalFormsEl.value = String(val);
      return val - 1;
    }
    function decreaseTotalForms() {
      totalFormsEl.value = String(Math.max(0, getNextFormIndex() - 1));
    }

    // ===== Cargar productos =====
    async function loadProducts(page = 1) {
      productsContainer.innerHTML = `<div class="text-center p-3"><div class="spinner-border"></div></div>`;
      const q = searchInput?.value?.trim() || "";
      const filterType = typeFilter?.value || "all"; // all | simple | variants
      const stockFilter = inStockOnly?.checked ? "in_stock" : "";

      const url = new URL(productsApi, window.location.origin);
      if (q) url.searchParams.set("q", q);
      if (filterType && filterType !== "all") url.searchParams.set("type", filterType);
      if (stockFilter) url.searchParams.set("stock", stockFilter);
      url.searchParams.set("page", page);

      try {
        const resp = await fetch(url, { credentials: "same-origin" });
        if (!resp.ok) throw new Error("Error al cargar productos");
        const data = await resp.json();
        renderProducts(data.products || [], data.page || 1, data.num_pages || 1);
      } catch (err) {
        console.error(err);
        productsContainer.innerHTML = `<div class="text-center text-danger">Error al cargar productos.</div>`;
      }
    }

    function renderProducts(products, page, numPages) {
      if (!products.length) {
        productsContainer.innerHTML = `<div class="text-center text-muted">No hay productos disponibles.</div>`;
        paginationContainer.innerHTML = "";
        return;
      }

      const html = products.map(p => renderProductCard(p)).join("");
      productsContainer.innerHTML = html;
      renderPagination(page, numPages);
      attachListeners();
    }

    function renderPagination(page, numPages) {
      if (numPages <= 1) {
        paginationContainer.innerHTML = "";
        return;
      }
      let html = `<nav><ul class="pagination pagination-sm">`;
      for (let i = 1; i <= numPages; i++) {
        html += `<li class="page-item ${i === page ? 'active' : ''}">
                   <a class="page-link" href="#" data-page="${i}">${i}</a>
                 </li>`;
      }
      html += `</ul></nav>`;
      paginationContainer.innerHTML = html;
      paginationContainer.querySelectorAll("a.page-link").forEach(a => {
        a.addEventListener("click", e => {
          e.preventDefault();
          loadProducts(Number(a.dataset.page));
        });
      });
    }

    function renderProductCard(p) {
      const hasVariants = Array.isArray(p.variants) && p.variants.length > 0;
      const img = p.image ? escapeHtml(p.image) : "/static/img/no-image.png";
      const priceDisplay = fmtCOP(p.price || 0);
      const stock = p.stock !== null ? p.stock : "-";

      let variantsHtml = "";
      if (hasVariants) {
        variantsHtml = `
          <table class="table table-sm table-borderless align-middle mb-0">
            <tbody>
              ${p.variants.map(v => {
                const variantPrice = v.price && parseFloat(v.price) > 0 ? v.price : p.price;
                return `
                  <tr>
                    <td>${escapeHtml(v.label)}</td>
                    <td class="text-end">${fmtCOP(variantPrice)}</td>
                    <td class="text-muted">Stock: ${escapeHtml(v.stock)}</td>
                    <td style="width:70px;"><input type="number" min="1" value="1" class="form-control form-control-sm variant-qty-input"></td>
                    <td>
                      <button class="btn btn-sm btn-primary btn-add-variant" 
                              data-product='${escapeHtml(JSON.stringify({
                                id: p.id, name: p.name, sku: p.sku
                              }))}'
                              data-variant='${escapeHtml(JSON.stringify({
                                id: v.id, label: v.label, stock: v.stock, price: variantPrice
                              }))}'>
                          Agregar
                      </button>
                    </td>
                  </tr>`;
              }).join("")}
            </tbody>
          </table>
        `;
      }

      return `
        <div class="col-12 col-md-6 col-lg-4">
          <div class="card h-100 shadow-sm">
            <img src="${img}" class="card-img-top" alt="${escapeHtml(p.name)}" style="height:130px; object-fit:cover;">
            <div class="card-body">
              <h6 class="card-title mb-1">${escapeHtml(p.name)}</h6>
              <div class="small text-muted mb-1">SKU: ${escapeHtml(p.sku)}</div>
              <div class="small text-muted mb-2">Stock: ${stock}</div>
              ${!hasVariants ? `
                <div class="mb-2">Precio: <strong>${priceDisplay}</strong></div>
                <div class="d-flex gap-2">
                  <input type="number" min="1" value="1" class="form-control form-control-sm simple-qty" style="width:80px;">
                  <button class="btn btn-sm btn-primary btn-add-simple" 
                          data-product='${escapeHtml(JSON.stringify({
                            id: p.id, name: p.name, sku: p.sku, price: p.price, stock: p.stock
                          }))}'>
                    Agregar
                  </button>
                </div>
              ` : variantsHtml}
            </div>
          </div>
        </div>
      `;
    }

    function attachListeners() {
      productsContainer.querySelectorAll(".btn-add-simple").forEach(btn => {
        btn.addEventListener("click", e => {
          e.preventDefault();
          const product = JSON.parse(btn.dataset.product || "{}");
          const qty = Math.max(1, Number(btn.closest(".d-flex").querySelector(".simple-qty").value));
          if (qty > product.stock) {
            alert(`Stock disponible: ${product.stock}`);
            return;
          }
          addItem(product, null, qty);
        });
      });

      productsContainer.querySelectorAll(".btn-add-variant").forEach(btn => {
        btn.addEventListener("click", e => {
          e.preventDefault();
          const product = JSON.parse(btn.dataset.product || "{}");
          const variant = JSON.parse(btn.dataset.variant || "{}");
          const row = btn.closest("tr");
          const qtyInput = row.querySelector(".variant-qty-input");
          const qty = Math.max(1, Number(qtyInput.value || 1));
          if (qty > variant.stock) {
            alert(`Stock disponible: ${variant.stock}`);
            return;
          }
          addItem(product, variant, qty);
        });
      });
    }

    function addItem(product, variant, qty) {
      const key = variant ? `${product.id}::${variant.id}` : `p::${product.id}`;
      if (previewMap.has(key)) {
        const row = previewMap.get(key);
        row.qty += qty;
        updatePreviewRow(row);
        updateFormQuantity(row.formIndex, row.qty);
      } else {
        const formIndex = increaseTotalForms();
        const row = {
          key,
          product_id: product.id,
          product_name: product.name,
          sku: product.sku,
          variant_id: variant ? variant.id : "",
          variant_label: variant ? variant.label : "",
          unit_price: variant ? variant.price : product.price,
          qty: qty,
          formIndex: formIndex
        };
        insertFormsetForm(row);
        insertPreviewRow(row);
        previewMap.set(key, row);
      }
      recalcTotals();
    }

    function insertFormsetForm(row) {
      const tpl = emptyTemplateTextarea.value || "";
      const html = tpl.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#039;/g, "'");
      const newForm = html.replace(/__prefix__/g, row.formIndex);
      itemsFormsContainer.insertAdjacentHTML("beforeend", newForm);

      const base = `${prefix}-${row.formIndex}`;
      itemsFormsContainer.querySelector(`[name="${base}-product"]`).value = row.product_id;
      itemsFormsContainer.querySelector(`[name="${base}-variant"]`).value = row.variant_id || "";
      itemsFormsContainer.querySelector(`[name="${base}-quantity"]`).value = row.qty;
      itemsFormsContainer.querySelector(`[name="${base}-unit_price"]`).value = row.unit_price;
    }

    function insertPreviewRow(row) {
      const tr = document.createElement("tr");
      tr.dataset.key = row.key;
      tr.innerHTML = `
        <td></td>
        <td>
          <div class="small">${escapeHtml(row.product_name)}</div>
          ${row.variant_label ? `<div class="text-muted small">${escapeHtml(row.variant_label)}</div>` : ""}
          <div class="small text-muted">SKU: ${escapeHtml(row.sku)}</div>
        </td>
        <td class="text-center"><input type="number" min="1" value="${row.qty}" class="form-control form-control-sm preview-qty" style="width:80px;"></td>
        <td class="text-end">${fmtCOP(row.unit_price)}</td>
        <td class="text-end subtotal">${fmtCOP(row.unit_price * row.qty)}</td>
        <td><button class="btn btn-sm btn-outline-danger btn-remove-item">&times;</button></td>
      `;
      tableBody.appendChild(tr);

      tr.querySelector(".preview-qty").addEventListener("input", e => {
        const v = Math.max(1, Number(e.target.value || 1));
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
      });
    }

    function updatePreviewRow(row) {
      const tr = tableBody.querySelector(`tr[data-key="${row.key}"]`);
      if (!tr) return;
      tr.querySelector(".preview-qty").value = row.qty;
      tr.querySelector(".subtotal").textContent = fmtCOP(row.unit_price * row.qty);
    }

    function updateFormQuantity(index, qty) {
      const el = itemsFormsContainer.querySelector(`[name="${prefix}-${index}-quantity"]`);
      if (el) el.value = qty;
    }

    function recalcTotals() {
      let total = 0;
      previewMap.forEach(r => total += r.unit_price * r.qty);
      totalDisplay.textContent = fmtCOP(total);
      const minDep = Math.round(total * 0.2);
      minDepositDisplay.textContent = fmtCOP(minDep);
      const dep = parseNumberSafe(amountDepositedInput.value || 0);
      dueMessage.textContent = total === 0 ? "Seleccione productos para calcular vencimiento." :
        dep >= minDep ? "Reserva válida por 30 días hábiles." : "Reserva válida por 3 días hábiles (abono mínimo 20%).";
    }

    // ===== Eventos =====
    searchInput?.addEventListener("input", () => loadProducts(1));
    clearSearchBtn?.addEventListener("click", () => { searchInput.value = ""; loadProducts(1); });
    typeFilter?.addEventListener("change", () => loadProducts(1));
    inStockOnly?.addEventListener("change", () => loadProducts(1));
    amountDepositedInput?.addEventListener("input", recalcTotals);

    reservationForm?.addEventListener("submit", e => {
      if (previewMap.size === 0) {
        e.preventDefault();
        alert("Debe agregar al menos un producto.");
      }
    });

    // Inicial
    loadProducts(1);
    recalcTotals();
  })();
});
