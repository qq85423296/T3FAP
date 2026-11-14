const CONTENT_SOURCES = [
  { id: "pages", label: "GitHub Pages", url: "./index.json" },
  { id: "raw", label: "GitHub Raw", url: "https://raw.githubusercontent.com/qq85423296/T3FAP/main/content/help/index.json" },
];
const CACHE_KEY = "t3fap:public-help:v1";
const REFRESH_INTERVAL = 5 * 60 * 1000;
const MAX_JSON_LENGTH = 2_000_000;
const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*$/;
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const INTERNAL_LINK_PATTERN = /^\/guide(?:\/([a-z0-9][a-z0-9-]*))?(?:#([A-Za-z0-9][A-Za-z0-9_-]*))?$/;
const LEGACY_SLUGS = {
  "quick-start/6-step-flow": "getting-started",
  "platform/overview": "monitor",
  "platform/resource-search": "resources",
  "platform/my-drive": "drive",
  "platform/task-center": "tasks",
  "platform/monitor": "monitor",
  "platform/plugins-and-settings": "plugins",
  "plugin-spec/general": "plugins",
  "plugin-spec/notification": "plugins",
  "plugin-spec/resource-search": "plugins",
  "plugin-spec/drive-adapter": "plugins",
  "plugin-spec/task-executor": "plugins",
  "examples/standard-io": "plugins",
  "faq/troubleshooting": "faq",
  "ops/integration": "install",
};

const elements = {
  article: document.querySelector("#help-article"),
  loading: document.querySelector("#help-loading"),
  error: document.querySelector("#help-error"),
  errorMessage: document.querySelector("#help-error-message"),
  source: document.querySelector("#help-source"),
  warning: document.querySelector("#help-warning"),
  retry: document.querySelector("#help-retry"),
  errorRetry: document.querySelector("#help-error-retry"),
  nav: document.querySelector("#help-nav"),
  outline: document.querySelector("#help-outline-content"),
  search: document.querySelector("#help-search-input"),
  searchResults: document.querySelector("#help-search-results"),
  menuButton: document.querySelector("#help-menu-button"),
  menuClose: document.querySelector("#help-menu-close"),
  sidebar: document.querySelector("#help-sidebar"),
  backdrop: document.querySelector("#help-backdrop"),
  faqLink: document.querySelector("#help-faq-link"),
};

const state = {
  payload: null,
  source: "",
  searchIndex: [],
  loadingPromise: null,
  outlineObserver: null,
};

function fail(label, message) {
  throw new Error(`${label}: ${message}`);
}

function object(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(label, "必须是对象");
  return value;
}

function text(value, label, { optional = false, empty = false, max = 4000 } = {}) {
  if (value === undefined && optional) return undefined;
  if (typeof value !== "string") fail(label, "必须是字符串");
  const result = value.trim();
  if (!empty && !result) fail(label, "不能为空");
  if (result.length > max) fail(label, `不能超过 ${max} 个字符`);
  return result;
}

function list(value, label, { optional = false, empty = false, max = 100 } = {}) {
  if (value === undefined && optional) return undefined;
  if (!Array.isArray(value)) fail(label, "必须是数组");
  if (!empty && value.length === 0) fail(label, "不能为空数组");
  if (value.length > max) fail(label, `不能超过 ${max} 项`);
  return value;
}

function stringList(value, label, options = {}) {
  return list(value, label, options)?.map((item, index) => text(item, `${label}[${index}]`, { max: 1000 }));
}

function boolean(value, label, { optional = false } = {}) {
  if (value === undefined && optional) return undefined;
  if (typeof value !== "boolean") fail(label, "必须是布尔值");
  return value;
}

function choice(value, choices, label, { optional = false } = {}) {
  if (value === undefined && optional) return undefined;
  if (!choices.includes(value)) fail(label, `必须是 ${choices.join("、")} 之一`);
  return value;
}

function safeLink(value, label, { optional = false } = {}) {
  if (value === undefined && optional) return undefined;
  const link = text(value, label, { max: 2000 });
  if (INTERNAL_LINK_PATTERN.test(link)) return link;
  try {
    const url = new URL(link);
    if (url.protocol !== "https:" || url.username || url.password) fail(label, "仅允许安全的内部链接或不含凭据的 HTTPS 地址");
    return url.href;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith(label)) throw error;
    fail(label, "不是有效链接");
  }
}

function normalizeAction(value, label) {
  const item = object(value, label);
  return {
    label: text(item.label, `${label}.label`, { max: 200 }),
    to: safeLink(item.to, `${label}.to`),
    variant: choice(item.variant, ["primary", "secondary", "ghost"], `${label}.variant`, { optional: true }),
    external: boolean(item.external, `${label}.external`, { optional: true }),
  };
}

function normalizeTip(value, label) {
  if (value === undefined) return undefined;
  const item = object(value, label);
  return {
    tone: choice(item.tone, ["info", "success", "warning", "error"], `${label}.tone`),
    title: text(item.title, `${label}.title`, { max: 300 }),
    text: text(item.text, `${label}.text`),
  };
}

function normalizeParamRow(value, label, depth = 0) {
  if (depth > 3) fail(label, "参数层级最多为 3 层");
  const item = object(value, label);
  return {
    name: text(item.name, `${label}.name`, { max: 200 }),
    type: text(item.type, `${label}.type`, { max: 100 }),
    required: boolean(item.required, `${label}.required`),
    defaultValue: text(item.defaultValue, `${label}.defaultValue`, { empty: true, max: 1000 }),
    description: text(item.description, `${label}.description`),
    example: text(item.example, `${label}.example`, { empty: true, max: 2000 }),
    children: list(item.children, `${label}.children`, { optional: true, max: 100 })?.map((row, index) => normalizeParamRow(row, `${label}.children[${index}]`, depth + 1)),
  };
}

function normalizeBlock(value, label) {
  const item = object(value, label);
  const type = choice(item.type, ["hero", "paragraph", "bullet-list", "callout", "code", "param-table", "card-grid", "meta-grid", "step-list", "faq-list"], `${label}.type`);

  if (type === "hero") {
    return {
      type,
      title: text(item.title, `${label}.title`, { max: 300 }),
      subtitle: text(item.subtitle, `${label}.subtitle`),
      actions: list(item.actions, `${label}.actions`, { optional: true, max: 8 })?.map((action, index) => normalizeAction(action, `${label}.actions[${index}]`)),
      badges: stringList(item.badges, `${label}.badges`, { optional: true, max: 12 }),
    };
  }
  if (type === "paragraph") return { type, text: text(item.text, `${label}.text`) };
  if (type === "bullet-list") return { type, items: stringList(item.items, `${label}.items`, { max: 100 }) };
  if (type === "callout") {
    return {
      type,
      tone: choice(item.tone, ["info", "success", "warning", "error"], `${label}.tone`),
      title: text(item.title, `${label}.title`, { max: 300 }),
      text: text(item.text, `${label}.text`),
    };
  }
  if (type === "code") {
    return {
      type,
      language: choice(item.language, ["json", "javascript", "shell", "text"], `${label}.language`),
      title: text(item.title, `${label}.title`, { optional: true, max: 300 }),
      description: text(item.description, `${label}.description`, { optional: true }),
      code: text(item.code, `${label}.code`, { max: 30000 }),
      variant: choice(item.variant, ["example", "success", "error"], `${label}.variant`, { optional: true }),
      collapsible: boolean(item.collapsible, `${label}.collapsible`, { optional: true }),
      defaultWrapped: boolean(item.defaultWrapped, `${label}.defaultWrapped`, { optional: true }),
    };
  }
  if (type === "param-table") {
    return {
      type,
      title: text(item.title, `${label}.title`, { optional: true, max: 300 }),
      description: text(item.description, `${label}.description`, { optional: true }),
      rows: list(item.rows, `${label}.rows`, { max: 100 }).map((row, index) => normalizeParamRow(row, `${label}.rows[${index}]`)),
    };
  }
  if (type === "card-grid") {
    return {
      type,
      columns: choice(item.columns, [2, 3, 4], `${label}.columns`, { optional: true }),
      items: list(item.items, `${label}.items`, { max: 24 }).map((value, index) => {
        const rowLabel = `${label}.items[${index}]`;
        const card = object(value, rowLabel);
        return {
          title: text(card.title, `${rowLabel}.title`, { max: 300 }),
          description: text(card.description, `${rowLabel}.description`),
          icon: text(card.icon, `${rowLabel}.icon`, { optional: true, max: 100 }),
          to: safeLink(card.to, `${rowLabel}.to`, { optional: true }),
          actionLabel: text(card.actionLabel, `${rowLabel}.actionLabel`, { optional: true, max: 200 }),
          notes: stringList(card.notes, `${rowLabel}.notes`, { optional: true, max: 12 }),
        };
      }),
    };
  }
  if (type === "meta-grid") {
    return {
      type,
      items: list(item.items, `${label}.items`, { max: 24 }).map((value, index) => {
        const rowLabel = `${label}.items[${index}]`;
        const meta = object(value, rowLabel);
        return {
          label: text(meta.label, `${rowLabel}.label`, { max: 200 }),
          value: text(meta.value, `${rowLabel}.value`),
          to: safeLink(meta.to, `${rowLabel}.to`, { optional: true }),
          external: boolean(meta.external, `${rowLabel}.external`, { optional: true }),
        };
      }),
    };
  }
  if (type === "step-list") {
    return {
      type,
      items: list(item.items, `${label}.items`, { max: 30 }).map((value, index) => {
        const rowLabel = `${label}.items[${index}]`;
        const step = object(value, rowLabel);
        return {
          title: text(step.title, `${rowLabel}.title`, { max: 300 }),
          description: text(step.description, `${rowLabel}.description`),
          details: stringList(step.details, `${rowLabel}.details`, { empty: true, max: 20 }),
          imageLabel: text(step.imageLabel, `${rowLabel}.imageLabel`, { optional: true, max: 300 }),
          tip: normalizeTip(step.tip, `${rowLabel}.tip`),
        };
      }),
    };
  }

  return {
    type,
    items: list(item.items, `${label}.items`, { max: 50 }).map((value, index) => {
      const rowLabel = `${label}.items[${index}]`;
      const faq = object(value, rowLabel);
      return {
        question: text(faq.question, `${rowLabel}.question`, { max: 500 }),
        answer: text(faq.answer, `${rowLabel}.answer`),
        steps: stringList(faq.steps, `${rowLabel}.steps`, { optional: true, empty: true, max: 20 }),
        tone: choice(faq.tone, ["info", "success", "warning", "error"], `${rowLabel}.tone`, { optional: true }),
        keywords: stringList(faq.keywords, `${rowLabel}.keywords`, { optional: true, max: 20 }),
      };
    }),
  };
}

function normalizeDocument(value, index) {
  const label = `items[${index}]`;
  const item = object(value, label);
  const slug = text(item.slug, `${label}.slug`, { empty: true, max: 100 });
  if (slug && !SLUG_PATTERN.test(slug)) fail(`${label}.slug`, "格式无效");
  const sectionIds = new Set();
  const sections = list(item.sections, `${label}.sections`, { max: 50 }).map((value, sectionIndex) => {
    const sectionLabel = `${label}.sections[${sectionIndex}]`;
    const section = object(value, sectionLabel);
    const id = text(section.id, `${sectionLabel}.id`, { max: 100 });
    if (!ID_PATTERN.test(id)) fail(`${sectionLabel}.id`, "格式无效");
    if (sectionIds.has(id)) fail(`${sectionLabel}.id`, `重复 ID ${id}`);
    sectionIds.add(id);
    return {
      id,
      title: text(section.title, `${sectionLabel}.title`, { max: 300 }),
      description: text(section.description, `${sectionLabel}.description`, { optional: true }),
      level: choice(section.level, [2, 3], `${sectionLabel}.level`),
      key: text(section.key, `${sectionLabel}.key`, { optional: true, max: 100 }),
      blocks: list(section.blocks, `${sectionLabel}.blocks`, { max: 60 }).map((block, blockIndex) => normalizeBlock(block, `${sectionLabel}.blocks[${blockIndex}]`)),
    };
  });
  return {
    id: text(item.id, `${label}.id`, { max: 100 }),
    slug,
    navTitle: text(item.navTitle, `${label}.navTitle`, { max: 200 }),
    title: text(item.title, `${label}.title`, { max: 300 }),
    subtitle: text(item.subtitle, `${label}.subtitle`),
    description: text(item.description, `${label}.description`, { optional: true }),
    group: text(item.group, `${label}.group`, { max: 100 }),
    icon: text(item.icon, `${label}.icon`, { optional: true, max: 100 }),
    searchTags: stringList(item.searchTags, `${label}.searchTags`, { optional: true, max: 30 }),
    sections,
  };
}

function normalizePayload(value) {
  const root = object(value, "帮助文档");
  if (root.schema_version !== 1) fail("schema_version", "必须为 1");
  text(root.updated_at, "updated_at", { max: 100 });
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(root.updated_at) || Number.isNaN(Date.parse(root.updated_at))) fail("updated_at", "必须是带时区的有效时间");
  const ids = new Set();
  const slugs = new Set();
  const items = list(root.items, "items", { max: 32 }).map(normalizeDocument);
  items.forEach((doc, index) => {
    if (ids.has(doc.id)) fail(`items[${index}].id`, `重复 ID ${doc.id}`);
    if (slugs.has(doc.slug)) fail(`items[${index}].slug`, `重复 slug ${doc.slug || "<首页>"}`);
    ids.add(doc.id);
    slugs.add(doc.slug);
  });
  if (items.filter((doc) => doc.slug === "").length !== 1) fail("items", "必须且只能有一篇 slug 为空字符串的帮助首页");
  return { schema_version: 1, updated_at: root.updated_at, items };
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function docUrl(slug = "", sectionId = "") {
  const url = new URL(window.location.href);
  url.search = "";
  if (slug) url.searchParams.set("doc", slug);
  url.hash = sectionId ? `#${sectionId}` : "";
  return url;
}

function relativeUrl(url) {
  return `${url.pathname}${url.search}${url.hash}`;
}

function makeLink(label, to, className = "") {
  const anchor = element("a", className, label);
  const internal = typeof to === "string" ? to.match(INTERNAL_LINK_PATTERN) : null;
  if (internal) {
    anchor.href = relativeUrl(docUrl(internal[1] || "", internal[2] || ""));
    anchor.dataset.helpDoc = "true";
  } else {
    anchor.href = to;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
  }
  return anchor;
}

function collectStrings(value, output = []) {
  if (typeof value === "string") output.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectStrings(item, output));
  else if (value && typeof value === "object") Object.values(value).forEach((item) => collectStrings(item, output));
  return output;
}

function buildSearchIndex() {
  state.searchIndex = state.payload.items.flatMap((doc) => doc.sections.map((section) => ({
    doc,
    section,
    text: [doc.title, doc.navTitle, doc.subtitle, ...(doc.searchTags || []), section.title, section.description || "", ...section.blocks.flatMap((block) => collectStrings(block))].join(" ").replace(/\s+/g, " "),
  })));
}

function formatUpdatedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

function setStatus(message, warning = "", showRetry = false) {
  elements.source.textContent = message;
  elements.warning.textContent = warning;
  elements.warning.hidden = !warning;
  elements.retry.hidden = !showRetry;
}

function readCache() {
  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    return raw ? normalizePayload(JSON.parse(raw)) : null;
  } catch {
    try { window.localStorage.removeItem(CACHE_KEY); } catch { /* Storage can be unavailable in an embedded browser. */ }
    return null;
  }
}

function writeCache(payload) {
  try {
    window.localStorage.setItem(CACHE_KEY, JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

async function fetchSource(source) {
  const url = new URL(source.url, window.location.href);
  url.searchParams.set("_", Date.now().toString());
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url.href, { cache: "no-store", credentials: "omit", signal: controller.signal, referrerPolicy: "no-referrer" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const raw = await response.text();
    if (raw.length > MAX_JSON_LENGTH) throw new Error("文档快照超过大小限制");
    return normalizePayload(JSON.parse(raw));
  } finally {
    window.clearTimeout(timeout);
  }
}

function applyPayload(payload, source, { preserveScroll = true } = {}) {
  const changed = !state.payload || state.payload.updated_at !== payload.updated_at;
  state.payload = payload;
  state.source = source;
  if (changed) {
    buildSearchIndex();
    renderNavigation();
    renderRoute({ preserveScroll });
  }
  return changed;
}

async function loadHelp() {
  if (state.loadingPromise) return state.loadingPromise;
  state.loadingPromise = (async () => {
    setStatus("正在读取在线教程…", "", false);
    const errors = [];
    for (const source of CONTENT_SOURCES) {
      try {
        const payload = await fetchSource(source);
        const persisted = writeCache(payload);
        applyPayload(payload, source.id);
        elements.error.hidden = true;
        setStatus(
          `${source.label} · 文档更新于 ${formatUpdatedAt(payload.updated_at)}`,
          persisted ? "" : "内容已显示，但浏览器未能保存本机缓存。",
          false,
        );
        return;
      } catch (error) {
        errors.push(`${source.label}: ${error instanceof Error ? error.message : String(error)}`);
        console.warn(`[T3FAP help] ${source.label} 读取失败`, error);
      }
    }

    if (state.payload) {
      setStatus(`仍显示上次读取的文档 · 更新于 ${formatUpdatedAt(state.payload.updated_at)}`, "在线更新失败，请检查网络后重试。", true);
      return;
    }

    const cached = readCache();
    if (cached) {
      applyPayload(cached, "cache", { preserveScroll: false });
      elements.error.hidden = true;
      setStatus(`本机缓存 · 文档更新于 ${formatUpdatedAt(cached.updated_at)}`, "GitHub Pages 和 Raw 暂时都无法读取。", true);
      return;
    }

    elements.loading.hidden = true;
    elements.article.hidden = true;
    elements.error.hidden = false;
    elements.errorMessage.textContent = "GitHub Pages 和 Raw 都无法读取，且没有可用的本机缓存。请检查网络后重新读取。";
    setStatus("在线教程读取失败", "没有可显示的文档。", true);
    console.error("[T3FAP help] 所有内容源均失败", errors);
  })().finally(() => {
    state.loadingPromise = null;
  });
  return state.loadingPromise;
}

function renderNavigation() {
  const home = state.payload.items.find((doc) => doc.slug === "");
  const homeLink = makeLink(home.navTitle, "/guide", "help-nav__home");
  const groups = new Map();
  state.payload.items.filter((doc) => doc.slug).forEach((doc) => {
    if (!groups.has(doc.group)) groups.set(doc.group, []);
    groups.get(doc.group).push(doc);
  });
  const groupNodes = [...groups.entries()].map(([group, docs]) => {
    const wrapper = element("div", "help-nav__group");
    wrapper.append(element("strong", "", group));
    docs.forEach((doc) => wrapper.append(makeLink(doc.navTitle, `/guide/${doc.slug}`)));
    return wrapper;
  });
  elements.nav.replaceChildren(homeLink, ...groupNodes);
  elements.faqLink.href = relativeUrl(docUrl("faq"));
  elements.faqLink.dataset.helpDoc = "true";
}

function updateActiveNavigation(slug) {
  elements.nav.querySelectorAll("a[data-help-doc]").forEach((anchor) => {
    const url = new URL(anchor.href);
    const active = (url.searchParams.get("doc") || "") === slug;
    if (active) anchor.setAttribute("aria-current", "page");
    else anchor.removeAttribute("aria-current");
  });
}

function renderCallout(block, extraClass = "") {
  const wrapper = element("div", `help-callout help-callout--${block.tone} ${extraClass}`.trim());
  wrapper.setAttribute("role", "note");
  wrapper.append(element("strong", "", block.title), element("p", "", block.text));
  return wrapper;
}

function renderCode(block) {
  const figure = element("figure", `help-code${block.variant ? ` help-code--${block.variant}` : ""}`);
  const caption = element("figcaption");
  caption.append(element("span", "", block.title || block.language.toUpperCase()));
  const copy = element("button", "", "复制");
  copy.type = "button";
  copy.addEventListener("click", async () => {
    copy.disabled = true;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(block.code);
      copy.textContent = "已复制";
    } catch {
      copy.textContent = "复制失败，请手动选择";
    } finally {
      window.setTimeout(() => { copy.textContent = "复制"; copy.disabled = false; }, 2200);
    }
  });
  caption.append(copy);
  figure.append(caption);
  if (block.description) figure.append(element("p", "help-code__description", block.description));
  const pre = element("pre", block.defaultWrapped ? "is-wrapped" : "");
  pre.append(element("code", "", block.code));
  figure.append(pre);
  if (!block.collapsible) return figure;
  const details = element("details", "help-code-details");
  details.append(element("summary", "", block.title || "查看代码"), figure);
  return details;
}

function renderParamRows(rows, tbody, depth = 0) {
  rows.forEach((row) => {
    const tr = element("tr");
    [depth ? `${"　".repeat(depth)}↳ ${row.name}` : row.name, row.type, row.required ? "是" : "否", row.defaultValue || "—", row.description, row.example || "—"].forEach((value) => tr.append(element("td", "", value)));
    tbody.append(tr);
    if (row.children) renderParamRows(row.children, tbody, depth + 1);
  });
}

function renderBlock(block) {
  if (block.type === "hero") {
    const wrapper = element("div", "help-block help-guide-hero");
    wrapper.append(element("h2", "", block.title), element("p", "", block.subtitle));
    if (block.badges?.length) {
      const badges = element("div", "help-badges");
      block.badges.forEach((badge) => badges.append(element("span", "", badge)));
      wrapper.append(badges);
    }
    if (block.actions?.length) {
      const actions = element("div", "help-actions");
      block.actions.forEach((action) => actions.append(makeLink(action.label, action.to, `help-button${action.variant === "primary" ? " help-button--primary" : action.variant === "ghost" ? " help-button--ghost" : ""}`)));
      wrapper.append(actions);
    }
    return wrapper;
  }
  if (block.type === "paragraph") return element("p", "help-block help-paragraph", block.text);
  if (block.type === "bullet-list") {
    const listNode = element("ul", "help-block help-bullet-list");
    block.items.forEach((item) => listNode.append(element("li", "", item)));
    return listNode;
  }
  if (block.type === "callout") {
    const node = renderCallout(block, "help-block");
    return node;
  }
  if (block.type === "code") {
    const node = renderCode(block);
    node.classList.add("help-block");
    return node;
  }
  if (block.type === "card-grid") {
    const grid = element("div", `help-block help-card-grid help-card-grid--${block.columns || 2}`);
    block.items.forEach((card) => {
      const node = card.to ? makeLink("", card.to, "help-card") : element("article", "help-card");
      node.append(element("h3", "", card.title), element("p", "", card.description));
      if (card.notes?.length) {
        const notes = element("ul");
        card.notes.forEach((note) => notes.append(element("li", "", note)));
        node.append(notes);
      }
      if (card.to) node.append(element("span", "help-card__action", `${card.actionLabel || "查看详情"} →`));
      grid.append(node);
    });
    return grid;
  }
  if (block.type === "meta-grid") {
    const grid = element("dl", "help-block help-meta-grid");
    block.items.forEach((item) => {
      const wrapper = element("div");
      wrapper.append(element("dt", "", item.label));
      const dd = element("dd");
      if (item.to) dd.append(makeLink(item.value, item.to));
      else dd.textContent = item.value;
      wrapper.append(dd);
      grid.append(wrapper);
    });
    return grid;
  }
  if (block.type === "step-list") {
    const listNode = element("ol", "help-block help-step-list");
    block.items.forEach((step) => {
      const item = element("li", "help-step");
      const content = element("div");
      content.append(element("h3", "", step.title), element("p", "", step.description));
      if (step.details.length) {
        const details = element("ul");
        step.details.forEach((detail) => details.append(element("li", "", detail)));
        content.append(details);
      }
      if (step.imageLabel) content.append(element("p", "help-step__image-label", `图示：${step.imageLabel}`));
      if (step.tip) content.append(renderCallout(step.tip, "help-step__tip"));
      item.append(element("span", "help-sr-only", "步骤"), content);
      listNode.append(item);
    });
    return listNode;
  }
  if (block.type === "faq-list") {
    const listNode = element("div", "help-block help-faq-list");
    block.items.forEach((faq) => {
      const details = element("details");
      details.append(element("summary", "", faq.question));
      const content = element("div");
      content.append(element("p", "", faq.answer));
      if (faq.steps?.length) {
        const steps = element("ol");
        faq.steps.forEach((step) => steps.append(element("li", "", step)));
        content.append(steps);
      }
      details.append(content);
      listNode.append(details);
    });
    return listNode;
  }
  if (block.type === "param-table") {
    const wrapper = element("div", "help-block");
    if (block.title) wrapper.append(element("h3", "", block.title));
    if (block.description) wrapper.append(element("p", "", block.description));
    const scroll = element("div", "help-table-wrap");
    const table = element("table", "help-table");
    const head = element("thead");
    const headRow = element("tr");
    ["名称", "类型", "必填", "默认值", "说明", "示例"].forEach((label) => headRow.append(element("th", "", label)));
    head.append(headRow);
    const body = element("tbody");
    renderParamRows(block.rows, body);
    table.append(head, body);
    scroll.append(table);
    wrapper.append(scroll);
    return wrapper;
  }
  return element("p", "help-block", "此内容块暂不支持显示。");
}

function renderOutline(doc) {
  const title = element("strong", "", "本页内容");
  const nav = element("nav");
  doc.sections.forEach((section) => {
    const anchor = makeLink(section.title, `/guide/${doc.slug}#${section.id}`);
    anchor.dataset.sectionLink = section.id;
    nav.append(anchor);
  });
  elements.outline.replaceChildren(title, nav);
  state.outlineObserver?.disconnect();
  if (!("IntersectionObserver" in window)) return;
  state.outlineObserver = new IntersectionObserver((entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (!visible) return;
    nav.querySelectorAll("a").forEach((anchor) => anchor.classList.toggle("is-active", anchor.dataset.sectionLink === visible.target.id));
  }, { rootMargin: "-100px 0px -65% 0px", threshold: 0 });
  doc.sections.forEach((section) => {
    const node = document.getElementById(section.id);
    if (node) state.outlineObserver.observe(node);
  });
}

function renderDocument(doc) {
  const article = elements.article;
  const breadcrumb = element("p", "help-breadcrumb", `帮助中心 / ${doc.group} / ${doc.navTitle}`);
  const header = element("header", "help-doc-header");
  header.append(element("p", "help-doc-header__group", doc.group), element("h1", "", doc.title), element("p", "help-doc-header__subtitle", doc.subtitle));
  if (doc.description) header.append(element("p", "help-doc-header__description", doc.description));
  const sectionNodes = doc.sections.map((section) => {
    const node = element("section", "help-doc-section");
    node.id = section.id;
    node.append(element(`h${section.level}`, "", section.title));
    if (section.description) node.append(element("p", "help-doc-section__description", section.description));
    section.blocks.forEach((block) => node.append(renderBlock(block)));
    return node;
  });

  const index = state.payload.items.findIndex((item) => item.id === doc.id);
  const previous = state.payload.items[index - 1];
  const next = state.payload.items[index + 1];
  const prevNext = element("nav", "help-prev-next");
  prevNext.setAttribute("aria-label", "上一篇和下一篇");
  if (previous) {
    const anchor = makeLink("", `/guide/${previous.slug}`);
    anchor.append(element("small", "", "← 上一篇"), element("strong", "", previous.navTitle));
    prevNext.append(anchor);
  } else prevNext.append(element("span"));
  if (next) {
    const anchor = makeLink("", `/guide/${next.slug}`);
    anchor.append(element("small", "", "下一篇 →"), element("strong", "", next.navTitle));
    prevNext.append(anchor);
  } else prevNext.append(element("span"));

  const footer = element("footer", "help-doc-footer");
  footer.append(document.createTextNode(`文档更新于 ${formatUpdatedAt(state.payload.updated_at)} · `));
  footer.append(makeLink("在 GitHub 查看内容源", "https://github.com/qq85423296/T3FAP/blob/main/content/help/index.json"));
  article.replaceChildren(breadcrumb, header, ...sectionNodes, prevNext, footer);
  article.hidden = false;
  elements.loading.hidden = true;
  elements.error.hidden = true;
  document.title = `${doc.title} · T3FAP 帮助中心`;
  updateActiveNavigation(doc.slug);
  renderOutline(doc);
}

function renderNotFound(slug) {
  const header = element("header", "help-doc-header");
  header.append(element("p", "help-doc-header__group", "404 / HELP"), element("h1", "", "没有找到这篇文档"), element("p", "help-doc-header__subtitle", `地址中的文档标识“${slug}”不存在，可能已更名或下线。`));
  const actions = element("div", "help-actions");
  actions.append(makeLink("返回帮助首页", "/guide", "help-button help-button--primary"), makeLink("查看常见问题", "/guide/faq", "help-button"));
  elements.article.replaceChildren(header, actions);
  elements.article.hidden = false;
  elements.loading.hidden = true;
  elements.error.hidden = true;
  elements.outline.replaceChildren(element("strong", "", "本页内容"), element("p", "", "这篇文档不存在。"));
  document.title = "文档不存在 · T3FAP 帮助中心";
  updateActiveNavigation("__not_found__");
}

function requestedSlug() {
  return new URL(window.location.href).searchParams.get("doc") || "";
}

function routeSectionId() {
  const raw = window.location.hash.replace(/^#/, "");
  try { return decodeURIComponent(raw); } catch { return raw; }
}

function scrollToRouteTarget(smooth = false) {
  const id = routeSectionId();
  window.requestAnimationFrame(() => {
    if (id) {
      const target = document.getElementById(id);
      if (target) {
        target.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
        return;
      }
    }
    window.scrollTo({ top: 0, behavior: "auto" });
  });
}

function renderRoute({ preserveScroll = false, smooth = false } = {}) {
  if (!state.payload) return;
  const scrollY = window.scrollY;
  let slug = requestedSlug();
  if (LEGACY_SLUGS[slug]) {
    slug = LEGACY_SLUGS[slug];
    const url = docUrl(slug, decodeURIComponent(window.location.hash.replace(/^#/, "")));
    window.history.replaceState({}, "", relativeUrl(url));
  }
  const doc = state.payload.items.find((item) => item.slug === slug);
  if (doc) renderDocument(doc);
  else renderNotFound(slug);
  if (preserveScroll) window.requestAnimationFrame(() => window.scrollTo({ top: scrollY, behavior: "auto" }));
  else scrollToRouteTarget(smooth);
}

function navigate(url, { replace = false, smooth = true } = {}) {
  if (replace) window.history.replaceState({}, "", relativeUrl(url));
  else window.history.pushState({}, "", relativeUrl(url));
  closeSearch();
  closeMenu();
  renderRoute({ smooth });
}

function closeSearch() {
  elements.searchResults.hidden = true;
  elements.search.setAttribute("aria-expanded", "false");
}

function renderSearchResults() {
  const query = elements.search.value.trim().toLocaleLowerCase("zh-CN");
  if (!query || !state.payload) {
    closeSearch();
    return;
  }
  const tokens = query.split(/\s+/).filter(Boolean);
  const results = state.searchIndex.map((item) => {
    const haystack = item.text.toLocaleLowerCase("zh-CN");
    if (!tokens.every((token) => haystack.includes(token))) return null;
    let score = 0;
    const docTitle = item.doc.title.toLocaleLowerCase("zh-CN");
    const sectionTitle = item.section.title.toLocaleLowerCase("zh-CN");
    tokens.forEach((token) => {
      if (docTitle.includes(token)) score += 40;
      if (sectionTitle.includes(token)) score += 30;
      if (item.doc.navTitle.toLocaleLowerCase("zh-CN").includes(token)) score += 20;
      score += 5;
    });
    const firstIndex = Math.min(...tokens.map((token) => {
      const index = haystack.indexOf(token);
      return index < 0 ? Number.POSITIVE_INFINITY : index;
    }));
    const start = Number.isFinite(firstIndex) ? Math.max(0, firstIndex - 36) : 0;
    return { ...item, score, snippet: item.text.slice(start, start + 120) };
  }).filter(Boolean).sort((a, b) => b.score - a.score).slice(0, 8);

  if (!results.length) {
    elements.searchResults.replaceChildren(element("p", "help-search-empty", "没有找到匹配内容，试试“转存”“定时”或“播放”。"));
  } else {
    const buttons = results.map((result) => {
      const button = element("button", "help-search-result");
      button.type = "button";
      button.append(element("strong", "", result.section.title), element("span", "", result.doc.navTitle), element("small", "", result.snippet));
      button.addEventListener("click", () => {
        elements.search.value = "";
        navigate(docUrl(result.doc.slug, result.section.id));
      });
      return button;
    });
    elements.searchResults.replaceChildren(...buttons);
  }
  elements.searchResults.hidden = false;
  elements.search.setAttribute("aria-expanded", "true");
}

function openMenu() {
  elements.sidebar.classList.add("is-open");
  elements.menuButton.setAttribute("aria-expanded", "true");
  elements.backdrop.hidden = false;
  document.body.style.overflow = "hidden";
  elements.menuClose.focus();
}

function closeMenu() {
  const wasOpen = elements.sidebar.classList.contains("is-open");
  elements.sidebar.classList.remove("is-open");
  elements.menuButton.setAttribute("aria-expanded", "false");
  elements.backdrop.hidden = true;
  document.body.style.overflow = "";
  if (wasOpen && window.innerWidth < 1024) elements.menuButton.focus();
}

document.addEventListener("click", (event) => {
  const anchor = event.target.closest("a[data-help-doc]");
  if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  navigate(new URL(anchor.href));
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".help-search")) closeSearch();
});

elements.search.addEventListener("input", renderSearchResults);
elements.search.addEventListener("focus", renderSearchResults);
elements.menuButton.addEventListener("click", openMenu);
elements.menuClose.addEventListener("click", closeMenu);
elements.backdrop.addEventListener("click", closeMenu);
elements.retry.addEventListener("click", loadHelp);
elements.errorRetry.addEventListener("click", loadHelp);

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  closeSearch();
  closeMenu();
  elements.search.blur();
});

window.addEventListener("popstate", () => renderRoute());
window.addEventListener("hashchange", () => scrollToRouteTarget(true));
window.addEventListener("resize", () => {
  if (window.innerWidth >= 1024) closeMenu();
});
window.addEventListener("online", () => { void loadHelp(); });
window.setInterval(() => {
  if (document.visibilityState === "visible" && navigator.onLine) void loadHelp();
}, REFRESH_INTERVAL);

void loadHelp();
