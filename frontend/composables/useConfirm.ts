import { reactive, readonly } from "vue";

export type ConfirmTone = "danger" | "primary";
export type ConfirmIcon = "info" | "warning" | "trash";

export interface ConfirmOptions {
  /** Título do cartão. Padrão: "Zona de risco". */
  title?: string;
  /** Pergunta principal, ex.: `Deseja excluir "Elétrica"?`. */
  message: string;
  /** Texto de apoio menor (consequência da ação). */
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** `danger` pinta o botão de confirmação de vermelho. */
  tone?: ConfirmTone;
  icon?: ConfirmIcon;
}

interface ConfirmState {
  open: boolean;
  title: string;
  message: string;
  detail: string;
  confirmLabel: string;
  cancelLabel: string;
  tone: ConfirmTone;
  icon: ConfirmIcon;
}

/**
 * Estado único (um diálogo por aplicação). O `ConfirmDialog` fica montado em
 * `app.vue`; qualquer tela chama `useConfirm().confirm(...)` e recebe uma
 * Promise<boolean> — sem `window.confirm`, que não segue o design do Hub.
 */
const state = reactive<ConfirmState>({
  open: false,
  title: "Zona de risco",
  message: "",
  detail: "",
  confirmLabel: "Excluir",
  cancelLabel: "Cancelar",
  tone: "danger",
  icon: "info",
});

let resolver: ((value: boolean) => void) | null = null;

function resolve(value: boolean): void {
  const current = resolver;
  resolver = null;
  state.open = false;
  current?.(value);
}

export function useConfirm() {
  function confirm(options: ConfirmOptions | string): Promise<boolean> {
    // Uma nova confirmação cancela a anterior (nunca deixa Promise pendente).
    if (resolver) resolve(false);

    const opts: ConfirmOptions = typeof options === "string" ? { message: options } : options;
    state.open = true;
    state.title = opts.title ?? "Zona de risco";
    state.message = opts.message;
    state.detail = opts.detail ?? "";
    state.confirmLabel = opts.confirmLabel ?? "Excluir";
    state.cancelLabel = opts.cancelLabel ?? "Cancelar";
    state.tone = opts.tone ?? "danger";
    state.icon = opts.icon ?? "info";

    return new Promise<boolean>((resolvePromise) => {
      resolver = resolvePromise;
    });
  }

  return {
    state: readonly(state),
    confirm,
    accept: () => resolve(true),
    cancel: () => resolve(false),
  };
}
