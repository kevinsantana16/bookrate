/* ──────────────────────────────────────────────
   main.js — BookRate
   • Busca em tempo real com debounce
   • Paginação via AJAX
   • Votos via fetch sem reload de página
   • Comentários / Resenhas (AJAX)
   • Lista de leitura (AJAX)
   • Alternância de abas no login
   • Toggle de visibilidade de senha
   • CSRF token em todas as requisições
   ────────────────────────────────────────────── */

"use strict";

// ── ESTADO GLOBAL (inicializado pelo template home.html) ──
// window.ESTADO = { pagina, totalPaginas, filtro }

// ── CSRF TOKEN ─────────────────────────────────────────
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : "";
}

// ── DEBOUNCE ────────────────────────────────────────────
function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

// ── AUTO-DISMISS FLASH MESSAGES ──────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.5s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 500);
    }, 4000);
  });
});

// ────────────────────────────────────────────────────────
//  LOGIN — alternância de abas
// ────────────────────────────────────────────────────────
function switchTab(tab) {
  const formLogin    = document.getElementById("form-login");
  const formCadastro = document.getElementById("form-cadastro");
  const tabLogin     = document.getElementById("tab-login");
  const tabCadastro  = document.getElementById("tab-cadastro");

  if (!formLogin) return; // Não está na página de login

  if (tab === "login") {
    formLogin.classList.remove("hidden");
    formCadastro.classList.add("hidden");
    tabLogin.classList.add("active");
    tabCadastro.classList.remove("active");
  } else {
    formCadastro.classList.remove("hidden");
    formLogin.classList.add("hidden");
    tabCadastro.classList.add("active");
    tabLogin.classList.remove("active");
  }
}

// ────────────────────────────────────────────────────────
//  LOGIN — toggle visibilidade da senha
// ────────────────────────────────────────────────────────
function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isHidden = input.type === "password";
  input.type = isHidden ? "text" : "password";
  const icon = btn.querySelector("i");
  if (icon) {
    icon.className = isHidden ? "fas fa-eye-slash" : "fas fa-eye";
  }
}

// ────────────────────────────────────────────────────────
//  HOME — busca em tempo real
// ────────────────────────────────────────────────────────

// Handler com debounce de 300ms
const onSearch = debounce(function () {
  const q = document.getElementById("search-input")?.value ?? "";
  const clearBtn = document.getElementById("search-clear");
  if (clearBtn) clearBtn.style.display = q ? "block" : "none";
  buscarLivros(q, 1);
}, 300);

function clearSearch() {
  const input = document.getElementById("search-input");
  if (input) input.value = "";
  const clearBtn = document.getElementById("search-clear");
  if (clearBtn) clearBtn.style.display = "none";
  buscarLivros("", 1);
}

function mudarPagina(novaPagina) {
  if (!window.ESTADO) return;
  const { filtro } = window.ESTADO;
  buscarLivros(filtro, novaPagina);
}

async function buscarLivros(q, pagina) {
  const grid = document.getElementById("cards-grid");
  if (!grid) return;

  // Feedback visual de carregamento
  grid.style.opacity = "0.4";
  grid.style.pointerEvents = "none";

  try {
    const url = `/api/livros?q=${encodeURIComponent(q)}&page=${pagina}`;
    const resp = await fetch(url, {
      headers: { "X-CSRFToken": getCsrfToken() },
    });
    if (!resp.ok) throw new Error("Erro na API");
    const data = await resp.json();

    // Atualiza estado global
    window.ESTADO = { pagina: data.pagina, totalPaginas: data.total_paginas, filtro: q };

    renderizarCards(data.livros, q);
    atualizarPaginacao(data.pagina, data.total_paginas);
    atualizarStats(data.total_livros, data.pagina, data.total_paginas);
  } catch (err) {
    console.error("Erro ao buscar livros:", err);
  } finally {
    grid.style.opacity = "1";
    grid.style.pointerEvents = "auto";
  }
}

function renderizarCards(livros, filtro) {
  const grid = document.getElementById("cards-grid");
  if (!grid) return;

  if (livros.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" id="empty-state">
        <i class="fas fa-search"></i>
        <p>Nenhum livro encontrado${filtro ? ` para "<strong>${escapeHtml(filtro)}</strong>"` : "."}</p>
      </div>`;
    return;
  }

  grid.innerHTML = livros.map((livro) => {
    const votoYes = livro.meu_voto === 1 ? "voted" : "";
    const votoNo  = livro.meu_voto === 0 ? "voted" : "";

    // Capa
    const coverHtml = livro.capa_url
      ? `<img src="${escapeHtml(livro.capa_url)}" alt="Capa" class="cover-img" loading="lazy"
             onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"/>
         <div class="cover-fallback" style="display:none"><i class="fas fa-book"></i></div>`
      : `<div class="cover-fallback"><i class="fas fa-book"></i></div>`;

    const langBadge = livro.idioma
      ? `<span class="lang-badge">${escapeHtml(livro.idioma.toUpperCase())}</span>` : "";

    // Descrição
    const descHtml = livro.descricao
      ? `<p class="card-desc">${escapeHtml(livro.descricao)}</p>` : "";

    // Metadados
    const metaItems = [
      livro.editora       ? `<span class="meta-item" title="Editora"><i class="fas fa-building"></i> ${escapeHtml(livro.editora)}</span>` : "",
      livro.total_paginas ? `<span class="meta-item" title="Páginas"><i class="fas fa-file-alt"></i> ${escapeHtml(String(livro.total_paginas))} pág.</span>` : "",
      livro.data_publicacao ? `<span class="meta-item" title="Publicação"><i class="fas fa-calendar-alt"></i> ${escapeHtml(String(livro.data_publicacao).slice(0,4))}</span>` : "",
    ].join("");
    const metaHtml = metaItems ? `<div class="card-meta">${metaItems}</div>` : "";

    // Categorias
    const cats = Array.isArray(livro.categorias) ? livro.categorias.slice(0, 3) : [];
    const tagsHtml = cats.length
      ? `<div class="card-tags">${cats.map(c => `<span class="tag">${escapeHtml(c)}</span>`).join("")}</div>` : "";

    // Lista de leitura
    const sl = livro.status_leitura || "";
    const readingHtml = `
      <div class="reading-status-wrap">
        <select class="reading-status-select" id="reading-${livro.id}"
                onchange="atualizarListaLeitura(${livro.id}, this.value)" title="Lista de leitura">
          <option value="" ${!sl ? 'selected' : ''}>📚 Adicionar à lista</option>
          <option value="quero_ler" ${sl === 'quero_ler' ? 'selected' : ''}>📖 Quero Ler</option>
          <option value="lendo" ${sl === 'lendo' ? 'selected' : ''}>📕 Lendo</option>
          <option value="lido" ${sl === 'lido' ? 'selected' : ''}>✅ Lido</option>
        </select>
      </div>`;

    return `
      <article class="book-card" id="card-${livro.id}" data-livro-id="${livro.id}">
        <a href="/livro/${livro.id}" class="card-cover-link">
          <div class="card-cover">
            ${coverHtml}
            ${langBadge}
          </div>
        </a>
        <div class="card-body">
          <a href="/livro/${livro.id}" class="card-title-link">
            <h2 class="card-title">${escapeHtml(livro.titulo)}</h2>
          </a>
          <p class="card-author"><i class="fas fa-pen-nib"></i> ${escapeHtml(livro.autor)}</p>
          ${descHtml}
          ${metaHtml}
          ${tagsHtml}
          ${readingHtml}
        </div>
        <div class="card-footer">
          <button class="vote-btn vote-yes ${votoYes}" id="btn-yes-${livro.id}"
            onclick="votar(${livro.id}, 1)" title="Recomendo">
            <i class="fas fa-thumbs-up"></i>
            <span class="vote-count" id="count-yes-${livro.id}">${livro.recomendo}</span>
          </button>
          <div class="vote-divider"></div>
          <button class="vote-btn vote-no ${votoNo}" id="btn-no-${livro.id}"
            onclick="votar(${livro.id}, 0)" title="Não Recomendo">
            <i class="fas fa-thumbs-down"></i>
            <span class="vote-count" id="count-no-${livro.id}">${livro.nao_recomendo}</span>
          </button>
        </div>
      </article>`;
  }).join("");
}

function atualizarPaginacao(pagina, totalPaginas) {
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const pageInfo = document.getElementById("page-info");

  if (btnPrev) {
    btnPrev.disabled = pagina <= 1;
    btnPrev.onclick = () => mudarPagina(pagina - 1);
  }
  if (btnNext) {
    btnNext.disabled = pagina >= totalPaginas;
    btnNext.onclick = () => mudarPagina(pagina + 1);
  }
  if (pageInfo) {
    pageInfo.innerHTML = `Página <strong>${pagina}</strong> de <strong>${totalPaginas}</strong>`;
  }
}

function atualizarStats(total, pagina, totalPaginas) {
  const el = document.getElementById("stat-total");
  const elPag = document.getElementById("stat-pagina");
  const elTotPags = document.getElementById("stat-total-pags");
  if (el)       el.textContent = total;
  if (elPag)    elPag.textContent = pagina;
  if (elTotPags) elTotPags.textContent = totalPaginas;
}

// ────────────────────────────────────────────────────────
//  HOME — votar
// ────────────────────────────────────────────────────────
async function votar(livroId, voto) {
  const btnYes = document.getElementById(`btn-yes-${livroId}`);
  const btnNo  = document.getElementById(`btn-no-${livroId}`);
  if (!btnYes || !btnNo) return;

  // Desabilita temporariamente para evitar double-click
  btnYes.disabled = true;
  btnNo.disabled  = true;

  try {
    const resp = await fetch("/api/votar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ livro_id: livroId, voto }),
    });

    if (!resp.ok) throw new Error("Erro ao votar");
    const data = await resp.json();

    // Atualiza contadores
    const countYes = document.getElementById(`count-yes-${livroId}`);
    const countNo  = document.getElementById(`count-no-${livroId}`);
    if (countYes) countYes.textContent = data.recomendo;
    if (countNo)  countNo.textContent  = data.nao_recomendo;

    // Atualiza destaque dos botões
    const meuVoto = data.meu_voto; // pode ser null (toggle off), 0 ou 1
    btnYes.classList.toggle("voted", meuVoto === 1);
    btnNo.classList.toggle("voted",  meuVoto === 0);

    // Micro-animação de feedback
    const btnAtivo = voto === 1 ? btnYes : btnNo;
    btnAtivo.style.transform = "scale(1.15)";
    setTimeout(() => (btnAtivo.style.transform = ""), 200);

  } catch (err) {
    console.error("Erro ao registrar voto:", err);
  } finally {
    btnYes.disabled = false;
    btnNo.disabled  = false;
  }
}

// ────────────────────────────────────────────────────────
//  LISTA DE LEITURA
// ────────────────────────────────────────────────────────
async function atualizarListaLeitura(livroId, status) {
  try {
    const resp = await fetch("/api/lista-leitura", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ livro_id: livroId, status: status || null }),
    });
    if (!resp.ok) throw new Error("Erro ao atualizar lista");

    // Micro-feedback visual
    const select = document.getElementById(`reading-${livroId}`);
    if (select) {
      select.style.boxShadow = "0 0 12px var(--accent-glow)";
      setTimeout(() => select.style.boxShadow = "", 400);
    }
  } catch (err) {
    console.error("Erro ao atualizar lista de leitura:", err);
  }
}

// ────────────────────────────────────────────────────────
//  COMENTÁRIOS / RESENHAS
// ────────────────────────────────────────────────────────
async function enviarComentario(livroId) {
  const input = document.getElementById("comment-input");
  const btn = document.getElementById("btn-comentar");
  if (!input || !btn) return;

  const texto = input.value.trim();
  if (!texto) return;

  btn.disabled = true;

  try {
    const resp = await fetch("/api/comentar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ livro_id: livroId, texto }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(err.error || "Erro ao publicar resenha.");
      return;
    }

    const data = await resp.json();

    // Remover empty state se existir
    const emptyEl = document.getElementById("empty-comments");
    if (emptyEl) emptyEl.remove();

    // Adicionar comentário no topo da lista
    const list = document.getElementById("comments-list");
    if (list) {
      const commentHtml = `
        <div class="comment-card" id="comment-${data.id}" style="animation: slideIn 0.3s ease">
          <div class="comment-header">
            <span class="comment-author">
              <i class="fas fa-user-circle"></i> ${escapeHtml(data.username)}
              ${data.is_admin ? '<span class="badge-admin" style="font-size:0.6rem">Admin</span>' : ''}
            </span>
            <span class="comment-date">agora</span>
          </div>
          <p class="comment-text">${escapeHtml(data.texto)}</p>
          <button class="comment-delete" onclick="excluirComentario(${data.id})" title="Excluir">
            <i class="fas fa-trash"></i>
          </button>
        </div>`;
      list.insertAdjacentHTML("afterbegin", commentHtml);
    }

    // Limpar input
    input.value = "";
    const charCount = document.getElementById("comment-char-count");
    if (charCount) charCount.textContent = "0 / 2000";

  } catch (err) {
    console.error("Erro ao publicar resenha:", err);
  } finally {
    btn.disabled = false;
  }
}

async function excluirComentario(comentarioId) {
  if (!confirm("Excluir esta resenha?")) return;

  try {
    const resp = await fetch(`/api/comentario/${comentarioId}/excluir`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
    });

    if (!resp.ok) throw new Error("Erro ao excluir");

    const el = document.getElementById(`comment-${comentarioId}`);
    if (el) {
      el.style.transition = "opacity 0.3s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    }
  } catch (err) {
    console.error("Erro ao excluir comentário:", err);
  }
}

// ────────────────────────────────────────────────────────
//  UTIL — escape HTML para evitar XSS no render client-side
// ────────────────────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}
