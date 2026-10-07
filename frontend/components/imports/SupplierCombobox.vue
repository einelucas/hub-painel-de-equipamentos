<script setup lang="ts">
import { computed } from "vue";
import SearchableSelect from "~/components/ui/SearchableSelect.vue";
import type { Supplier } from "~/types/equipment";
import { sortSuppliers, supplierLabel } from "~/utils/suppliers";

const props = withDefaults(
  defineProps<{
    suppliers: Supplier[];
    modelValue: string;
    label: string;
    emptyLabel?: string;
    emptyValue?: string;
  }>(),
  { emptyLabel: "Manter sem fornecedor", emptyValue: "__NONE__" },
);
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const options = computed(() =>
  sortSuppliers(props.suppliers).map((supplier) => ({
    id: supplier.id,
    label: supplierLabel(supplier),
    description: supplier.tradeName ?? undefined,
    searchText: [supplier.corporateCode, supplier.legalName, supplier.tradeName]
      .filter(Boolean)
      .join(" "),
  })),
);
</script>

<template>
  <SearchableSelect
    :model-value="modelValue"
    :options="options"
    :label="label"
    placeholder="Digite o código ou nome"
    :empty-label="emptyLabel"
    :empty-value="emptyValue"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>
