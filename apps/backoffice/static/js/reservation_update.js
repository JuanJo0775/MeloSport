document.addEventListener("DOMContentLoaded", function () {
  const totalDisplay = document.getElementById("total-display");
  const minDepositDisplay = document.getElementById("min-deposit-display");
  const dueMessage = document.getElementById("due-message");
  const amountDepositedInput = document.getElementById("id_amount_deposited");

  function fmtCOP(n) {
    return "$ " + (Number(n) || 0).toLocaleString("es-CO");
  }

  function parsePrice(val) {
    let n = parseFloat(val);
    return isNaN(n) ? 0 : n;
  }

  function recalcTotals() {
    let total = 0;
    document.querySelectorAll("#selected-products-table tbody tr").forEach(tr => {
      const qtyCell = tr.querySelector("td.text-center");
      const unitCell = tr.querySelector("td.text-end:nth-child(4)");
      if (qtyCell && unitCell) {
        const qty = parsePrice(qtyCell.textContent);
        const unit = parsePrice(unitCell.textContent.replace(/[^0-9.,-]/g, ""));
        total += qty * unit;
      }
    });

    totalDisplay.textContent = fmtCOP(total);
    const minDep = Math.round(total * 0.2);
    minDepositDisplay.textContent = fmtCOP(minDep);

    const dep = parsePrice(amountDepositedInput?.value || 0);
    dueMessage.textContent = total === 0
      ? "Seleccione productos para calcular vencimiento."
      : dep >= minDep
        ? "Reserva válida por 30 días hábiles."
        : "Reserva válida por 3 días hábiles (abono mínimo 20%).";
  }

  amountDepositedInput?.addEventListener("input", recalcTotals);
  recalcTotals();
});
