<script setup lang="ts">
import { ElInput } from "element-plus";

/**
 * Campo de texto construído sobre o `ElInput` do Element Plus.
 * Atributos livres (`id`, `aria-*`, `maxlength`, `placeholder`, `disabled`)
 * caem no input nativo via o encaminhamento do próprio EP — o contrato
 * `for=` dos labels continua funcionando. `type="date"`/`"search"` seguem
 * nativos, apenas com o visual do EP.
 */
const props = defineProps<{ type?: string }>();
const model = defineModel<string | number>();
</script>

<template>
  <ElInput
    :type="props.type ?? 'text'"
    :model-value="model ?? ''"
    :validate-event="false"
    @update:model-value="model = $event"
  />
</template>
