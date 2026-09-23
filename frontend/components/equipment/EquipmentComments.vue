<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Eye,
  Heart,
  MessageSquareText,
  MoreHorizontal,
  Pencil,
  Reply,
  SendHorizontal,
  Trash2,
  X,
} from "lucide-vue-next";
import type { CatalogList, EquipmentComment } from "~/types/equipment";
import { formatDateTime } from "~/utils/format";

const props = defineProps<{ equipmentId: string }>();

const api = useApi();
const auth = useAuthStore();

const comments = ref<EquipmentComment[]>([]);
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const actionError = ref("");

const newText = ref("");
const editingId = ref<string | null>(null);
const editingText = ref("");
const deletingId = ref<string | null>(null);

const canWrite = auth.can("process:write");
const MAX_LENGTH = 4000;

const remainingCharacters = computed(() => MAX_LENGTH - newText.value.length);

const commentCountLabel = computed(() => {
  const count = comments.value.length;
  return `${count} ${count === 1 ? "comentário" : "comentários"}`;
});

function authorName(item: EquipmentComment): string {
  return item.author?.name ?? "Usuário removido";
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);

  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();

  return `${parts[0]![0] ?? ""}${parts.at(-1)?.[0] ?? ""}`.toUpperCase();
}

function composerInitials(): string {
  return initials(auth.user?.name ?? "Você");
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    comments.value = (
      await api.get<CatalogList<EquipmentComment>>(
        `/equipments/${props.equipmentId}/comments`,
      )
    ).items;
  } catch (caught) {
    error.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível carregar os comentários.";
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  const text = newText.value.trim();

  if (!text || busy.value) return;

  busy.value = true;
  actionError.value = "";

  try {
    await api.post(`/equipments/${props.equipmentId}/comments`, {
      text,
    });

    newText.value = "";
    await load();
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível publicar o comentário.";
  } finally {
    busy.value = false;
  }
}

function startEdit(item: EquipmentComment): void {
  deletingId.value = null;
  editingId.value = item.id;
  editingText.value = item.text;
}

function cancelEdit(): void {
  editingId.value = null;
  editingText.value = "";
}

async function saveEdit(item: EquipmentComment): Promise<void> {
  const text = editingText.value.trim();

  if (!text || busy.value) return;

  busy.value = true;
  actionError.value = "";

  try {
    await api.patch(`/equipments/${props.equipmentId}/comments/${item.id}`, {
      text,
    });

    editingId.value = null;
    editingText.value = "";
    await load();
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível salvar a edição.";
  } finally {
    busy.value = false;
  }
}

function requestDelete(item: EquipmentComment): void {
  editingId.value = null;
  deletingId.value = item.id;
}

function cancelDelete(): void {
  deletingId.value = null;
}

async function remove(item: EquipmentComment): Promise<void> {
  if (busy.value) return;

  busy.value = true;
  actionError.value = "";

  try {
    await api.delete(`/equipments/${props.equipmentId}/comments/${item.id}`);

    deletingId.value = null;
    await load();
  } catch (caught) {
    actionError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível excluir o comentário.";
  } finally {
    busy.value = false;
  }
}

function isOwn(item: EquipmentComment): boolean {
  return item.author?.id === auth.user?.id;
}

onMounted(load);
</script>

<template>
  <section class="comments-board">
    <header class="board-header">
      <div class="board-title-wrap">
        <div class="board-icon">
          <MessageSquareText :size="18" />
        </div>

        <div class="board-copy">
          <div class="board-title-row">
            <h2>Comentários</h2>
            <span v-if="!loading" class="board-count">
              {{ commentCountLabel }}
            </span>
          </div>

          <p>
            Conversa do equipamento. Use este espaço para registrar
            alinhamentos, decisões e observações.
          </p>
        </div>
      </div>

      <div class="board-badges">
        <span class="board-badge"> Sem anexos </span>
        <span class="board-badge board-badge--subtle">
          Histórico separado
        </span>
      </div>
    </header>

    <div v-if="loading" class="board-state" data-testid="comments-loading">
      <span class="spinner" />
      Carregando comentários...
    </div>

    <div v-else-if="error" class="board-error" role="alert">
      <MessageSquareText :size="22" />
      <div>
        <strong>Não foi possível carregar</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" class="ghost-btn" @click="load">
        Tentar novamente
      </button>
    </div>

    <template v-else>
      <div v-if="canWrite" class="main-composer">
        <div class="main-composer-avatar" aria-hidden="true">
          {{ composerInitials() }}
        </div>

        <form
          class="main-composer-card"
          data-testid="comment-form"
          @submit.prevent="submit"
        >
          <textarea
            v-model="newText"
            :maxlength="MAX_LENGTH"
            rows="3"
            placeholder="Escreva um comentário, atualização ou decisão..."
            aria-label="Novo comentário"
          />

          <div class="main-composer-footer">
            <span
              class="composer-count"
              :class="{
                'composer-count--warning': remainingCharacters <= 250,
              }"
            >
              {{ remainingCharacters }} caracteres restantes
            </span>

            <button
              type="submit"
              class="primary-btn"
              :disabled="!newText.trim() || busy"
              data-testid="comment-submit"
            >
              <SendHorizontal :size="14" />
              {{ busy ? "Publicando..." : "Comentar" }}
            </button>
          </div>
        </form>
      </div>

      <p v-if="actionError" class="action-notice" role="alert">
        {{ actionError }}
      </p>

      <div
        v-if="comments.length === 0"
        class="board-empty"
        data-testid="comments-empty"
      >
        <div class="board-empty-icon">
          <MessageSquareText :size="22" />
        </div>

        <div class="board-empty-copy">
          <strong>Nenhum comentário ainda</strong>
          <p>
            Quando alguém comentar sobre este equipamento, a conversa aparecerá
            aqui.
          </p>
        </div>
      </div>

      <div v-else class="comment-feed" data-testid="comment-list">
        <article
          v-for="item in comments"
          :key="item.id"
          class="comment-card"
          :class="{ 'comment-card--own': isOwn(item) }"
          :data-testid="`comment-${item.id}`"
        >
          <div class="comment-card-main">
            <header class="comment-card-header">
              <div class="comment-person">
                <div class="comment-avatar" aria-hidden="true">
                  {{ initials(authorName(item)) }}
                </div>

                <div class="comment-identity">
                  <div class="comment-name-row">
                    <strong>{{ authorName(item) }}</strong>

                    <span v-if="isOwn(item)" class="you-badge"> Você </span>

                    <span class="comment-time">
                      {{ formatDateTime(item.createdAt) }}
                    </span>
                  </div>

                  <span
                    v-if="item.updatedAt !== item.createdAt"
                    class="comment-edited"
                  >
                    Editado em {{ formatDateTime(item.updatedAt) }}
                  </span>
                </div>
              </div>

              <div class="comment-top-actions">
                <button
                  type="button"
                  class="icon-btn"
                  aria-label="Curtir comentário"
                >
                  <Heart :size="15" />
                </button>

                <button
                  type="button"
                  class="icon-btn"
                  aria-label="Responder comentário"
                >
                  <Reply :size="15" />
                </button>

                <button type="button" class="icon-btn" aria-label="Mais ações">
                  <MoreHorizontal :size="15" />
                </button>
              </div>
            </header>

            <div class="comment-body">
              <p v-if="editingId !== item.id" class="comment-text">
                {{ item.text }}
              </p>

              <div v-else class="comment-edit-box">
                <textarea
                  v-model="editingText"
                  :maxlength="MAX_LENGTH"
                  rows="4"
                  aria-label="Editar comentário"
                />

                <div class="comment-edit-footer">
                  <span class="edit-count">
                    {{ editingText.length }}/{{ MAX_LENGTH }}
                  </span>

                  <div class="inline-actions">
                    <button
                      type="button"
                      class="ghost-btn"
                      :disabled="busy"
                      @click="cancelEdit"
                    >
                      Cancelar
                    </button>

                    <button
                      type="button"
                      class="primary-btn"
                      :disabled="!editingText.trim() || busy"
                      @click="saveEdit(item)"
                    >
                      {{ busy ? "Salvando..." : "Salvar" }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div class="comment-card-meta">
              <span class="meta-item">
                <Eye :size="14" />
                <span>1</span>
              </span>

              <span class="meta-item meta-item--muted"> Conversa interna </span>
            </div>
          </div>

          <div class="comment-card-footer">
            <div class="footer-actions">
              <button type="button" class="footer-action">
                <Heart :size="15" />
                Curtir
              </button>

              <button type="button" class="footer-action">
                <Reply :size="15" />
                Responder
              </button>

              <template
                v-if="
                  isOwn(item) && editingId !== item.id && deletingId !== item.id
                "
              >
                <button
                  type="button"
                  class="footer-action"
                  @click="startEdit(item)"
                >
                  <Pencil :size="15" />
                  Editar
                </button>

                <button
                  type="button"
                  class="footer-action footer-action--danger"
                  :disabled="busy"
                  @click="requestDelete(item)"
                >
                  <Trash2 :size="15" />
                  Excluir
                </button>
              </template>
            </div>
          </div>

          <div v-if="deletingId === item.id" class="delete-box">
            <div class="delete-copy">
              <strong>Excluir este comentário?</strong>
              <span>Essa ação não pode ser desfeita.</span>
            </div>

            <div class="inline-actions">
              <button
                type="button"
                class="ghost-btn"
                :disabled="busy"
                @click="cancelDelete"
              >
                <X :size="14" />
                Cancelar
              </button>

              <button
                type="button"
                class="danger-btn"
                :disabled="busy"
                @click="remove(item)"
              >
                <Trash2 :size="14" />
                {{ busy ? "Excluindo..." : "Excluir" }}
              </button>
            </div>
          </div>

          <div v-if="canWrite" class="reply-mock">
            <div class="reply-mock-avatar" aria-hidden="true">
              {{ composerInitials() }}
            </div>

            <button
              type="button"
              class="reply-mock-input"
              aria-label="Responder comentário"
            >
              Escreva uma resposta e mencione outros com @
            </button>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.comments-board {
  display: grid;
  gap: 18px;

  padding: 20px;

  border-radius: 18px;

  background: #ffffff;

  border: 1px solid #dde4ed;

  box-shadow: 0 12px 28px rgb(29 48 76 / 5%);
}

/* =========================================================
   HEADER
   ========================================================= */

.board-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.board-title-wrap {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.board-icon {
  display: grid;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  place-items: center;

  border-radius: 10px;

  background: #edf2f8;
  color: #304f7e;
}

.board-copy {
  min-width: 0;
}

.board-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.board-title-row h2 {
  margin: 0;

  color: #18375c;

  font-size: 18px;
  font-weight: 760;
  line-height: 1.2;
}

.board-count {
  display: inline-flex;
  min-height: 22px;
  align-items: center;

  padding: 2px 9px;

  border: 1px solid #dde4ed;
  border-radius: 999px;

  background: #f6f8fb;
  color: #748197;

  font-size: 10px;
  font-weight: 700;
}

.board-copy p {
  margin: 6px 0 0;

  color: #7e899c;

  font-size: 12px;
  line-height: 1.5;
}

.board-badges {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.board-badge {
  display: inline-flex;
  min-height: 24px;
  align-items: center;

  padding: 3px 10px;

  border-radius: 999px;

  background: #edf3fb;
  color: #3b618e;

  font-size: 10px;
  font-weight: 700;
}

.board-badge--subtle {
  background: #f6f8fb;
  color: #8b96a5;
}

/* =========================================================
   STATES
   ========================================================= */

.board-state,
.board-error,
.board-empty {
  display: flex;
  min-height: 120px;
  align-items: center;
  justify-content: center;
  gap: 12px;

  border: 1px solid #e3e8ef;
  border-radius: 14px;

  background: #fafbfd;

  color: #748197;

  padding: 20px;
}

.board-error,
.board-empty {
  align-items: center;
}

.board-error > div,
.board-empty-copy {
  display: grid;
  gap: 4px;
}

.board-error strong,
.board-empty strong {
  color: #18375c;
  font-size: 12.5px;
  font-weight: 740;
}

.board-error p,
.board-empty p {
  margin: 0;
  color: #7e899c;
  font-size: 11px;
  line-height: 1.45;
}

.board-empty-icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;

  border-radius: 12px;

  background: #f1f4f8;
  color: #73839a;
}

/* =========================================================
   GLOBAL BUTTONS
   ========================================================= */

.primary-btn,
.ghost-btn,
.danger-btn {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;

  padding: 7px 12px;

  border-radius: 9px;

  font-family: inherit;
  font-size: 11px;
  font-weight: 700;

  transition:
    transform 0.15s ease,
    opacity 0.15s ease,
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.primary-btn {
  border: 1px solid #304f7e;
  background: #304f7e;
  color: #ffffff;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #29456f;
}

.ghost-btn {
  border: 1px solid #d9e0e9;
  background: #ffffff;
  color: #617187;
}

.ghost-btn:hover:not(:disabled) {
  background: #f1f4f8;
}

.danger-btn {
  border: 1px solid #ca6d67;
  background: #bf5e58;
  color: #fff;
}

.danger-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #cb6a64;
}

.primary-btn:disabled,
.ghost-btn:disabled,
.danger-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

/* =========================================================
   TOP COMPOSER
   ========================================================= */

.main-composer {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
}

.main-composer-avatar,
.comment-avatar,
.reply-mock-avatar {
  display: grid;
  place-items: center;

  border-radius: 50%;

  color: #18375c;
  font-weight: 760;
  user-select: none;
}

.main-composer-avatar {
  width: 42px;
  height: 42px;

  background: #e7eef8;

  font-size: 12px;
}

.main-composer-card {
  overflow: hidden;

  border: 1px solid #d9e0e9;
  border-radius: 14px;

  background: #ffffff;

  box-shadow: inset 0 1px 0 rgb(255 255 255 / 50%);
}

.main-composer-card textarea,
.comment-edit-box textarea {
  display: block;

  box-sizing: border-box;
  width: 100%;
  min-height: 108px;

  padding: 16px 16px 14px;

  border: 0;

  background: transparent;
  color: #34445b;

  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;

  outline: none;
  resize: vertical;
}

.main-composer-card textarea::placeholder,
.reply-mock-input {
  color: #9aa5b5;
}

.main-composer-footer,
.comment-edit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  min-height: 54px;
  padding: 9px 12px 9px 16px;

  border-top: 1px solid #edf1f5;

  background: #fbfcfd;
}

.composer-count,
.edit-count {
  color: #9aa4b2;
  font-size: 10px;
}

.composer-count--warning {
  color: #ffce7d;
  font-weight: 700;
}

.action-notice {
  margin: 0;
  padding: 11px 13px;

  border: 1px solid #f0d6d1;
  border-radius: 12px;

  background: #fff8f7;
  color: #a4453a;

  font-size: 11px;
}

/* =========================================================
   FEED
   ========================================================= */

.comment-feed {
  display: grid;
  gap: 16px;
}

.comment-card {
  overflow: hidden;

  border: 1px solid #dde4ed;
  border-radius: 16px;

  background: #ffffff;

  box-shadow: 0 8px 20px rgb(29 48 76 / 5%);
}

.comment-card--own {
  border-color: #cfd9e8;
}

.comment-card-main {
  padding: 16px 18px 12px;
}

.comment-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.comment-person {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.comment-avatar {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;

  background: #e7eef8;

  font-size: 11px;
}

.comment-identity {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.comment-name-row {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
}

.comment-name-row strong {
  color: #18375c;
  font-size: 14px;
  font-weight: 760;
}

.you-badge {
  display: inline-flex;
  min-height: 20px;
  align-items: center;

  padding: 1px 7px;

  border-radius: 999px;

  background: #edf3fb;
  color: #3b618e;

  font-size: 9px;
  font-weight: 700;
}

.comment-time {
  color: #97a1b0;
  font-size: 11px;
}

.comment-edited {
  color: #9aa4b2;
  font-size: 10px;
}

.comment-top-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
}

.icon-btn {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;

  border: 0;
  border-radius: 8px;

  background: transparent;
  color: #64768d;

  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.icon-btn:hover {
  background: #f1f4f8;
  color: #18375c;
}

.comment-body {
  padding: 18px 0 12px;
}

.comment-text {
  margin: 0;

  color: #465569;

  font-size: 16px;
  font-weight: 520;
  line-height: 1.65;

  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.comment-edit-box {
  overflow: hidden;

  border: 1px solid #d9e0e9;
  border-radius: 14px;

  background: #ffffff;
}

.comment-card-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;

  color: #75839a;
  font-size: 11px;
}

.meta-item--muted {
  color: #9aa4b2;
}

/* =========================================================
   FOOTER ACTIONS
   ========================================================= */

.comment-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;

  min-height: 62px;
  padding: 0 16px;

  border-top: 1px solid #edf1f5;
}

.footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.footer-action {
  display: inline-flex;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: 8px;

  padding: 8px 10px;

  border: 0;
  border-radius: 9px;

  background: transparent;
  color: #617187;

  font-family: inherit;
  font-size: 12px;
  font-weight: 650;

  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.footer-action:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
  color: #18375c;
}

.footer-action--danger:hover:not(:disabled) {
  background: #fff2f0;
  color: #a4453a;
}

.footer-action:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.delete-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;

  margin: 0 16px 14px;
  padding: 12px 13px;

  border: 1px solid #f0d6d1;
  border-radius: 12px;

  background: #fff8f7;
}

.delete-copy {
  display: grid;
  gap: 3px;
}

.delete-copy strong {
  color: #854238;
  font-size: 11.5px;
}

.delete-copy span {
  color: #9d7069;
  font-size: 10px;
}

.inline-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* =========================================================
   REPLY MOCK
   ========================================================= */

.reply-mock {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;

  padding: 0 16px 16px;
}

.reply-mock-avatar {
  width: 36px;
  height: 36px;

  background: #e7eef8;

  font-size: 10px;
}

.reply-mock-input {
  display: flex;
  width: 100%;
  min-height: 52px;
  align-items: center;

  padding: 0 16px;

  border: 1px solid #d9e0e9;
  border-radius: 12px;

  background: #ffffff;
  color: #8b96a5;

  font-family: inherit;
  font-size: 12px;
  text-align: left;

  transition:
    border-color 0.15s ease,
    background-color 0.15s ease,
    color 0.15s ease;
}

.reply-mock-input:hover {
  border-color: #b9c6d8;
  background: #f8fafc;
  color: #304f7e;
}

/* =========================================================
   RESPONSIVE
   ========================================================= */

@media (max-width: 860px) {
  .board-header {
    flex-direction: column;
  }

  .board-badges {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .comments-board {
    padding: 16px;
  }

  .main-composer,
  .reply-mock {
    grid-template-columns: 32px minmax(0, 1fr);
  }

  .main-composer-avatar,
  .reply-mock-avatar {
    width: 32px;
    height: 32px;
    font-size: 9px;
  }

  .comment-card-main {
    padding: 14px 14px 12px;
  }

  .comment-card-footer {
    padding: 0 12px;
  }

  .reply-mock {
    padding: 0 12px 12px;
  }

  .comment-card-header {
    flex-direction: column;
  }

  .comment-top-actions {
    align-self: flex-end;
  }

  .comment-text {
    font-size: 14px;
  }

  .delete-box {
    align-items: stretch;
    flex-direction: column;
    margin: 0 12px 12px;
  }

  .inline-actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }
}

@media (max-width: 560px) {
  .main-composer-footer,
  .comment-edit-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .primary-btn,
  .ghost-btn,
  .danger-btn {
    width: 100%;
  }

  .footer-actions {
    width: 100%;
    justify-content: space-between;
  }

  .footer-action {
    flex: 1 1 calc(50% - 8px);
  }
}
</style>
