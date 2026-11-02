<script setup lang="ts">
import { VCheckbox } from "vuetify/components";

/**
 * Checkbox compacto do Hub. O wrapper mantém o contrato booleano usado pelo
 * catálogo e deixa foco, teclado e estado indeterminado a cargo do Vuetify.
 */
const model = defineModel<boolean>({ default: false });

withDefaults(
  defineProps<{
    disabled?: boolean;
    readonly?: boolean;
    indeterminate?: boolean;
    label?: string;
  }>(),
  {
    disabled: false,
    readonly: false,
    indeterminate: false,
    label: undefined,
  },
);
</script>

<template>
  <VCheckbox
    v-model="model"
    class="hub-checkbox"
    color="primary"
    density="compact"
    hide-details
    :disabled="disabled"
    :readonly="readonly"
    :indeterminate="indeterminate"
    :label="label"
  />
</template>

<style scoped>
.hub-checkbox {
  flex: 0 0 auto;
}
</style>
