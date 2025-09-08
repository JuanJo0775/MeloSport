// static/js/reservation_update.js
document.addEventListener("DOMContentLoaded", function () {
  (function () {
    // ---------- helpers ----------
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

    // ---------- elems ----------
    const pageRoot = document.querySelector("#reservation-page");
    if (!pageRoot) return;

    const tableBody = pageRoot.querySelector("#selected-products-table tbody");
    const totalDisplay = pageRoot.querySelector("#total-display");
    const minDepositDisplay = pageRoot.querySelector("#min-deposit-display");
    const dueMessage = pageRoot.querySelector("#due-message");
    const amountDepositedInput = pageRoot.querySelector("#id_amount_deposited");
    const itemsFormsContainer = pageRoot.querySelector("#items-forms-container");

    if (!itemsFormsContainer) {
      // si no existe formset oculto, aún intentamos leer la tabla (fallback)
      console.warn("No se encontró items-forms-container. Usando fallback por tabla (menos fiable).");
    }

    // construir lista de forms a partir del formset oculto
    function buildFormRows() {
      const rows = [];
      if (!itemsFormsContainer) return rows;

      // Buscar todos los inputs unit_price dentro del container
      const unitInputs = Array.from(itemsFormsContainer.querySelectorAll("input[name$='-unit_price']"));

      // Para cada unit_input extraer el índice y buscar el quantity correspondiente
      unitInputs.forEach(unitInput => {
        const m = unitInput.name.match(/-(\d+)-unit_price$/);
        if (!m) return;
        const idx = Number(m[1]);
        const qtyInput = itemsFormsContainer.querySelector(`[name$='-${idx}-quantity']`);
        const productInput = itemsFormsContainer.querySelector(`[name$='-${idx}-product']`);
        const variantInput = itemsFormsContainer.querySelector(`[name$='-${idx}-variant']`);
        rows.push({
          idx,
          unitInput,
          qtyInput,
          productInput,
          variantInput
        });
      });

      // ordenar por índice ascendente (asegura correspondencia con tabla render)
      rows.sort((a, b) => a.idx - b.idx);
      return rows;
    }

    // recalcular totales basados en formset oculto
    function recalcTotals() {
      let total = 0;

      const rows = buildFormRows();

      if (rows.length > 0) {
        // recorremos rows y actualizamos subtotales en la tabla por posición
        const trNodes = tableBody ? Array.from(tableBody.querySelectorAll("tr")) : [];

        rows.forEach((r, pos) => {
          const qty = r.qtyInput ? Number(r.qtyInput.value || 0) : 0;
          // unit value: preferir value del input, si está vacío intentar parse del atributo value o textContent
          const rawUnit = (r.unitInput && (r.unitInput.value || r.unitInput.getAttribute("value") || r.unitInput.textContent)) || 0;
          const unit = parsePrice(rawUnit);
          const subtotal = Math.round(qty * unit);
          total += subtotal;

          // Actualizar la fila correspondiente en la tabla (si existe)
          const tr = trNodes[pos];
          if (tr) {
            // intentar encontrar la celda subtotal (última celda con clase text-end o por índice)
            let subtotalEl = tr.querySelector(".subtotal");
            if (!subtotalEl) {
              const tds = tr.querySelectorAll("td");
              subtotalEl = tds[tds.length - 1] || null;
            }
            if (subtotalEl) subtotalEl.textContent = fmtCOP(subtotal);

            // también actualizar el precio unitario visible (por si es necesario mantener consistencia)
            let unitEl = tr.querySelector(".unit-price");
            if (!unitEl) {
              const tds = tr.querySelectorAll("td");
              unitEl = tds[3] || null; // columna 4 esperada
            }
            if (unitEl) unitEl.textContent = fmtCOP(unit);
          }
        });
      } else {
        // fallback: si no hay formset oculto, intentar leer subtotales de la tabla y parsearlos robustamente
        if (tableBody) {
          const trNodes = Array.from(tableBody.querySelectorAll("tr"));
          trNodes.forEach(tr => {
            const tds = tr.querySelectorAll("td");
            if (!tds || tds.length < 4) return;
            const qty = parsePrice(tds[2].textContent || 0);
            const unit = parsePrice(tds[3].textContent || 0);
            const subtotal = Math.round(qty * unit);
            const subtotalEl = tds[tds.length - 1];
            if (subtotalEl) subtotalEl.textContent = fmtCOP(subtotal);
            total += subtotal;
          });
        }
      }

      // actualizar displays
      if (totalDisplay) totalDisplay.textContent = fmtCOP(total);
      const minDep = Math.round(total * 0.2);
      if (minDepositDisplay) minDepositDisplay.textContent = fmtCOP(minDep);

      const dep = parsePrice(amountDepositedInput ? amountDepositedInput.value : 0);
      if (dueMessage) {
        dueMessage.textContent = total === 0
          ? "Seleccione productos para calcular vencimiento."
          : (dep >= minDep
            ? "Reserva válida por 30 días hábiles."
            : "Reserva válida por 3 días hábiles (abono mínimo 20%).");
      }
    }

    // escuchar cambios en inputs del formset oculto (cantidad / precio) y en abono
    function attachListeners() {
      if (!itemsFormsContainer) return;
      // delegación: cualquier input dentro del container que cambie, recalculamos
      itemsFormsContainer.addEventListener("input", function (e) {
        const target = e.target;
        if (!target) return;
        if (target.name && (target.name.endsWith("-quantity") || target.name.endsWith("-unit_price"))) {
          // si cantidad o precio cambian, recalc
          recalcTotals();
        }
      });
    }

    // init
    attachListeners();
    amountDepositedInput?.addEventListener("input", recalcTotals);

    // Exponer para debug en la consola
    window.__reservation_recalcTotals = recalcTotals;

    // Primera ejecución
    recalcTotals();
  })();
});
