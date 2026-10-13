import type { useApi } from "~/composables/useApi";
import type { CatalogItem, CatalogList, EapNodeItem } from "~/types/equipment";

/**
 * Opções do filtro "Área": nós EAP ativos em que um equipamento pode estar
 * (Processo ou Área), no formato `código · nome`, ordenados pelo código.
 * Substitui o catálogo legado `/areas`, que não é mais gravado nos equipamentos.
 */
export async function loadEapLocationOptions(api: ReturnType<typeof useApi>): Promise<CatalogItem[]> {
  const nodes = (await api.get<CatalogList<EapNodeItem>>("/eap-nodes", { active: true })).items;
  return nodes
    .filter((node) => node.active && (node.level === "PROCESS" || node.level === "AREA"))
    .sort((a, b) => a.code.localeCompare(b.code, "pt-BR", { numeric: true }))
    .map((node) => ({ id: node.id, code: node.code, name: `${node.code} · ${node.name}`, active: node.active }));
}
