/**
 * Bloqueio de rolagem compartilhado por diálogos sobrepostos.
 *
 * Um contador evita que o fechamento de um modal interno libere a rolagem
 * enquanto o modal externo (ou um confirmação) ainda estiver aberto.
 */
let locks = 0;
let previousOverflow = "";

export function lockBodyScroll(): void {
  if (typeof document === "undefined") return;
  if (locks === 0) previousOverflow = document.body.style.overflow;
  locks += 1;
  document.body.style.overflow = "hidden";
}

export function unlockBodyScroll(): void {
  if (typeof document === "undefined" || locks === 0) return;
  locks -= 1;
  if (locks === 0) document.body.style.overflow = previousOverflow;
}
