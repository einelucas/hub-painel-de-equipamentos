<script setup lang="ts">
import { ElButton } from "element-plus";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/utils/cn";

/**
 * Botão padrão do Hub. Usa `ElButton` para carregamento, foco, teclado e
 * bloqueio de clique, mas mantém o contrato anterior (`variant`, `size`,
 * `type` nativo e `class`) para os consumidores existentes.
 */
const buttonVariants = cva("hub-button", {
  variants: {
    variant: {
      default: "hub-button--default",
      outline: "hub-button--outline",
      secondary: "hub-button--secondary",
      ghost: "hub-button--ghost",
      destructive: "hub-button--destructive",
      success: "hub-button--success",
      link: "hub-button--link",
    },
    size: {
      default: "hub-button--md",
      sm: "hub-button--sm",
      icon: "hub-button--icon",
      "icon-sm": "hub-button--icon-sm",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});

type ButtonVariants = VariantProps<typeof buttonVariants>;

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariants["variant"];
    size?: ButtonVariants["size"];
    /** Tipo nativo do botão (`submit` continua enviando o formulário). */
    type?: "button" | "submit" | "reset";
    class?: string;
    loading?: boolean;
    disabled?: boolean;
  }>(),
  {
    type: "button",
    variant: "default",
    size: "default",
    class: undefined,
    loading: false,
    disabled: false,
  },
);
</script>

<template>
  <ElButton
    data-slot="button"
    :native-type="props.type"
    :disabled="props.disabled || props.loading"
    :loading="props.loading"
    :aria-busy="props.loading || undefined"
    :class="cn(buttonVariants({ variant: props.variant, size: props.size }), props.class)"
  >
    <template v-if="props.loading" #loading>
      <span class="hub-button__spinner" aria-hidden="true" />
    </template>
    <slot />
  </ElButton>
</template>

<style scoped>
/* Element Plus define a base; estas regras preservam a identidade visual do Hub. */
.hub-button.el-button {
  gap: 6px;
  height: 36px;
  min-height: 36px;
  border: 1px solid transparent;
  border-radius: 9px;
  padding: 0 12px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.hub-button.el-button > span {
  gap: 6px;
}

.hub-button.el-button.hub-button--sm {
  height: 32px;
  min-height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  font-size: 12px;
}

.hub-button.el-button.hub-button--icon,
.hub-button.el-button.hub-button--icon-sm {
  width: 36px;
  padding: 0;
}

.hub-button.el-button.hub-button--icon-sm {
  width: 32px;
  height: 32px;
  min-height: 32px;
}

.hub-button.el-button.hub-button--default {
  border-color: #304f7e;
  background: #304f7e;
  color: #fff;
}

.hub-button.el-button.hub-button--default:not(.is-disabled):hover,
.hub-button.el-button.hub-button--default:not(.is-disabled):focus {
  border-color: #213758;
  background: #213758;
  color: #fff;
}

.hub-button.el-button.hub-button--outline {
  border-color: #d8e0ea;
  background: #fff;
  color: #34445a;
}

.hub-button.el-button.hub-button--outline:not(.is-disabled):hover,
.hub-button.el-button.hub-button--outline:not(.is-disabled):focus {
  border-color: #c5d0df;
  background: #f5f7fa;
  color: #263d5d;
}

.hub-button.el-button.hub-button--secondary {
  border-color: #e2e8f0;
  background: #eef2f7;
  color: #315889;
}

.hub-button.el-button.hub-button--secondary:not(.is-disabled):hover,
.hub-button.el-button.hub-button--secondary:not(.is-disabled):focus {
  border-color: #d5deea;
  background: #e3eaf4;
  color: #213758;
}

.hub-button.el-button.hub-button--ghost {
  border-color: transparent;
  background: transparent;
  color: #4b5c73;
}

.hub-button.el-button.hub-button--ghost:not(.is-disabled):hover,
.hub-button.el-button.hub-button--ghost:not(.is-disabled):focus {
  border-color: transparent;
  background: #eef2f7;
  color: #213758;
}

.hub-button.el-button.hub-button--destructive {
  border-color: #efc7c2;
  background: #fdf2f0;
  color: #a6372c;
}

.hub-button.el-button.hub-button--destructive:not(.is-disabled):hover,
.hub-button.el-button.hub-button--destructive:not(.is-disabled):focus {
  border-color: #e5b0a9;
  background: #fbe5e2;
  color: #8d2e25;
}

.hub-button.el-button.hub-button--success {
  border-color: #609346;
  background: #609346;
  color: #fff;
}

.hub-button.el-button.hub-button--success:not(.is-disabled):hover,
.hub-button.el-button.hub-button--success:not(.is-disabled):focus {
  border-color: #4e7a38;
  background: #4e7a38;
  color: #fff;
}

.hub-button.el-button.hub-button--link {
  height: auto;
  min-height: 0;
  border-color: transparent;
  padding: 0;
  background: transparent;
  color: #304f7e;
}

.hub-button.el-button.hub-button--link:not(.is-disabled):hover,
.hub-button.el-button.hub-button--link:not(.is-disabled):focus {
  border-color: transparent;
  background: transparent;
  color: #213758;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.hub-button.el-button:focus-visible {
  outline: 2px solid #304f7e;
  outline-offset: 2px;
}

.hub-button__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: hub-button-spin 0.8s linear infinite;
}

@keyframes hub-button-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .hub-button__spinner {
    animation-duration: 2.4s;
  }
}
</style>
