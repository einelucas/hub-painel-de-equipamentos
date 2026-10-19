<script setup lang="ts">
import type { PendingRequirement } from "~/types/equipment";

defineProps<{
  pending: PendingRequirement[];
  nextStageName: string | null;
}>();
</script>

<template>
  <div class="pending">
    <span v-if="!nextStageName" class="pending-badge pending-badge--done">Processo concluído</span>

    <span v-else-if="pending.length === 0" class="pending-badge pending-badge--ready">
      Pronto para {{ nextStageName }}
    </span>

    <template v-else>
      <span class="pending-caption">
        Falta para avançar
        <strong class="pending-stage">{{ nextStageName }}</strong>
      </span>

      <span v-for="item in pending" :key="item.code" class="pending-badge pending-badge--todo">
        {{ item.message }}
      </span>
    </template>
  </div>
</template>

<style scoped>
/*
 * Mesma linguagem visual dos demais badges do app (StageBadge, TipBadge,
 * DisciplineBadge): pílula arredondada, fundo tonal suave, texto curto em
 * 11px/750 e sem borda. Evita o bloco com borda e marcador que destoava da
 * tabela.
 *
 * Todos os badges ocupam a largura inteira da coluna, com a mesma altura
 * mínima de 26px (a mesma do DisciplineBadge/CriticalityBadge): assim o
 * tamanho não varia conforme o texto ("Concluído" x "Pronto para …").
 */
.pending {
  display: flex;
  width: 100%;
  min-width: 220px;
  max-width: 300px;
  flex-direction: column;
  gap: 5px;
  box-sizing: border-box;
}

.pending-badge {
  display: inline-flex;
  width: 100%;
  min-height: 26px;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 750;
  line-height: 1.35;
  text-align: center;
  white-space: normal;
}

/* Requisitos podem ser frases longas: quebram em mais de uma linha e alinham à esquerda. */
.pending-badge--todo {
  justify-content: flex-start;
  background: #fff3df;
  color: #9b6418;
  text-align: left;
}

.pending-badge--done {
  background: #eaf4e5;
  color: #477a32;
}

.pending-badge--ready {
  background: #e8f1fc;
  color: #2f5f9c;
}

.pending-caption {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: #8b96a5;
  font-size: 9.5px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.045em;
  text-transform: uppercase;
}

.pending-stage {
  color: #59677c;
  font-size: 10.5px;
  font-weight: 750;
  letter-spacing: 0;
  text-transform: none;
}
</style>
