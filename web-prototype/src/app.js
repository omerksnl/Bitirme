const channels = {
  atv: { name: "ATV", short: "A" },
  now: { name: "NOW", short: "N" },
  show: { name: "Show TV", short: "S" },
  halk: { name: "Halk TV", short: "H" },
  sozcu: { name: "Sözcü TV", short: "SZ" },
};

const agendaByChannel = {
  all: { Siyaset: 34, Ekonomi: 27, Dünya: 16, Toplum: 14, Sağlık: 9 },
  atv: { Siyaset: 38, Ekonomi: 24, Dünya: 14, Toplum: 16, Sağlık: 8 },
  now: { Siyaset: 31, Ekonomi: 33, Dünya: 15, Toplum: 13, Sağlık: 8 },
  show: { Siyaset: 21, Ekonomi: 18, Dünya: 13, Toplum: 37, Sağlık: 11 },
  halk: { Siyaset: 43, Ekonomi: 29, Dünya: 11, Toplum: 10, Sağlık: 7 },
  sozcu: { Siyaset: 40, Ekonomi: 31, Dünya: 10, Toplum: 12, Sağlık: 7 },
};

const topics = [
  { id: "politics", label: "Siyaset", count: 42 },
  { id: "economy", label: "Ekonomi", count: 31 },
  { id: "world", label: "Dünya", count: 19 },
  { id: "society", label: "Toplum", count: 17 },
  { id: "health", label: "Sağlık", count: 11 },
];

const economySubtopics = ["Enflasyon", "Faiz", "Döviz", "Piyasalar", "İstihdam"];

const news = [
  { id: 1, channel: "atv", time: "19:14", direction: "negative", title: "Akaryakıt fiyatlarında yeni artış beklentisi", summary: "Motorin fiyatlarında hafta içinde değişiklik bekleniyor." },
  { id: 2, channel: "now", time: "19:22", direction: "negative", title: "Gıda fiyatlarında aylık yükseliş", summary: "Temel gıda gruplarındaki fiyat hareketleri ele alındı." },
  { id: 3, channel: "show", time: "19:27", direction: "positive", title: "Kuru soğan fiyatları geriledi", summary: "Pazar tezgâhlarında fiyat düşüşü gözlendi." },
  { id: 4, channel: "halk", time: "19:36", direction: "negative", title: "Ulaşım maliyetlerindeki artış gündemde", summary: "Yeni maliyetlerin tüketici fiyatlarına etkisi tartışıldı." },
  { id: 5, channel: "sozcu", time: "19:41", direction: "positive", title: "Enerji maliyetlerinde sınırlı gerileme", summary: "Dış piyasalardaki düşüşün iç fiyatlara olası etkisi değerlendirildi." },
  { id: 6, channel: "atv", time: "19:48", direction: "negative", title: "Kira ve konut giderlerinde yükseliş", summary: "Büyükşehirlerdeki güncel kira fiyatları aktarıldı." },
  { id: 7, channel: "now", time: "19:53", direction: "positive", title: "Sebze arzında mevsimsel artış", summary: "Ürün miktarındaki artışın fiyatları düşürdüğü belirtildi." },
  { id: 8, channel: "halk", time: "20:07", direction: "negative", title: "Üretim maliyetleri üreticiyi zorluyor", summary: "Enerji ve ham madde giderlerindeki değişim incelendi." },
];

const state = { period: "daily", channel: "all", topic: "all", direction: "all" };

const app = document.querySelector("#app");
const channelFilter = document.querySelector("#channelFilter");
const topicFilter = document.querySelector("#topicFilter");

document.querySelectorAll(".period").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".period").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.period = button.dataset.period;
    renderRoute();
  });
});

channelFilter.addEventListener("change", (event) => {
  state.channel = event.target.value;
  renderRoute();
});

topicFilter.addEventListener("change", (event) => {
  state.topic = event.target.value;
  renderRoute();
});

window.addEventListener("hashchange", renderRoute);

function periodLabel() {
  return { daily: "Bugünün", monthly: "Bu Ayın", yearly: "Bu Yılın" }[state.period];
}

function renderRoute() {
  const route = location.hash.replace("#/", "") || "overview";
  document.querySelectorAll("nav a").forEach((link) => link.classList.toggle("active", link.dataset.nav === route.split("/")[0]));

  if (route === "inflation") renderInflation();
  else if (route === "channels") renderChannels();
  else if (route.startsWith("channel/")) renderChannel(route.split("/")[1]);
  else renderOverview();

  app.focus({ preventScroll: true });
}

function cloneTemplate(id) {
  const fragment = document.querySelector(id).content.cloneNode(true);
  app.replaceChildren(fragment);
}

function renderOverview() {
  cloneTemplate("#overviewTemplate");
  const selectedName = state.channel === "all" ? "Genel" : channels[state.channel].name;
  document.querySelector("#agendaTitle").textContent = `${periodLabel()} ${selectedName} Gündem Dağılımı`;
  renderAgenda();
  renderTopics();
}

function renderAgenda() {
  const chart = document.querySelector("#agendaChart");
  const distribution = agendaByChannel[state.channel] || agendaByChannel.all;
  chart.innerHTML = Object.entries(distribution).map(([label, value]) => `
    <div class="agenda-row">
      <span>${label}</span>
      <div class="agenda-track"><div class="agenda-fill" style="width:${value}%"></div></div>
      <strong>%${value}</strong>
    </div>
  `).join("");
}

function renderTopics() {
  const container = document.querySelector("#topicCards");
  container.innerHTML = topics.map((topic) => `
    <button class="topic-card ${state.topic === topic.id ? "active" : ""}" data-topic="${topic.id}">
      <strong>${topic.label}</strong>
      <span>${topic.count} haber</span>
    </button>
  `).join("");

  container.querySelectorAll(".topic-card").forEach((button) => {
    button.addEventListener("click", () => {
      state.topic = button.dataset.topic;
      topicFilter.value = state.topic;
      renderOverview();
    });
  });

  const area = document.querySelector("#subtopicArea");
  if (state.topic === "economy") {
    area.hidden = false;
    document.querySelector("#subtopicCards").innerHTML = economySubtopics.map((label) => `
      <button class="subtopic-card" data-subtopic="${label}"><strong>${label}</strong></button>
    `).join("");
    document.querySelectorAll(".subtopic-card").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.subtopic === "Enflasyon") location.hash = "#/inflation";
      });
    });
  }
}

function filteredNews(channel = state.channel) {
  return news.filter((item) => {
    const channelMatches = channel === "all" || item.channel === channel;
    const directionMatches = state.direction === "all" || item.direction === state.direction;
    return channelMatches && directionMatches;
  });
}

function renderInflation() {
  cloneTemplate("#inflationTemplate");
  document.querySelectorAll(".direction-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.direction === state.direction);
    button.addEventListener("click", () => {
      state.direction = button.dataset.direction;
      renderInflation();
    });
  });

  const visible = filteredNews("all");
  const positive = visible.filter((item) => item.direction === "positive");
  const negative = visible.filter((item) => item.direction === "negative");
  const columns = [];
  if (state.direction !== "negative") columns.push(impactColumn("positive", "Pozitif Etkileyenler", positive));
  if (state.direction !== "positive") columns.push(impactColumn("negative", "Negatif Etkileyenler", negative));
  const impact = document.querySelector("#impactColumns");
  impact.innerHTML = columns.join("");
  if (columns.length === 1) impact.style.gridTemplateColumns = "1fr";

  if (state.channel === "all") renderInflationChannelList();
  else renderInflationFeed(state.channel);
}

function impactColumn(type, title, items) {
  return `
    <article class="impact-column ${type}">
      <h2>${title}</h2>
      <p class="impact-count">${items.length} haber</p>
      ${items.slice(0, 3).map((item) => `
        <div class="compact-news">
          <p>${channels[item.channel].name} · ${item.time}</p>
          <h3>${item.title}</h3>
        </div>
      `).join("") || `<div class="empty-state">Haber bulunamadı.</div>`}
    </article>
  `;
}

function renderInflationChannelList() {
  document.querySelector("#lowerEyebrow").textContent = "Kanallar";
  document.querySelector("#lowerTitle").textContent = "Kanal Listesi";
  const container = document.querySelector("#inflationLowerContent");
  container.className = "channel-grid";
  container.innerHTML = Object.entries(channels).map(([id, channel]) => {
    const count = filteredNews(id).length;
    return channelCard(id, channel, count);
  }).join("");
  bindChannelCards(container);
}

function renderInflationFeed(channelId) {
  document.querySelector("#lowerEyebrow").textContent = "Haber akışı";
  document.querySelector("#lowerTitle").textContent = `${channels[channelId].name} — Enflasyon`;
  const container = document.querySelector("#inflationLowerContent");
  container.className = "news-feed";
  container.innerHTML = newsFeed(filteredNews(channelId));
}

function channelCard(id, channel, count) {
  return `
    <button class="channel-card" data-channel-id="${id}">
      <span class="channel-monogram">${channel.short}</span>
      <strong>${channel.name}</strong>
      <span>${count} haber</span>
    </button>
  `;
}

function bindChannelCards(container) {
  container.querySelectorAll(".channel-card").forEach((button) => {
    button.addEventListener("click", () => {
      state.channel = button.dataset.channelId;
      channelFilter.value = state.channel;
      location.hash = `#/channel/${state.channel}`;
    });
  });
}

function renderChannels() {
  cloneTemplate("#channelsTemplate");
  const container = document.querySelector("#allChannelCards");
  container.innerHTML = Object.entries(channels).map(([id, channel]) => channelCard(id, channel, news.filter((item) => item.channel === id).length)).join("");
  bindChannelCards(container);
}

function renderChannel(channelId) {
  const channel = channels[channelId];
  if (!channel) {
    location.hash = "#/channels";
    return;
  }
  cloneTemplate("#channelTemplate");
  document.querySelector("#channelBreadcrumb").textContent = channel.name;
  document.querySelector("#channelPageTitle").textContent = channel.name;
  document.querySelector("#channelFeed").innerHTML = newsFeed(filteredNews(channelId));
}

function newsFeed(items) {
  if (!items.length) return `<div class="empty-state">Bu seçim için haber bulunamadı.</div>`;
  return items.map((item) => `
    <article class="news-item">
      <time class="news-time">${item.time}</time>
      <div>
        <h2>${item.title}</h2>
        <p>${item.summary}</p>
      </div>
      <span class="badge ${item.direction}">${item.direction === "positive" ? "Pozitif" : "Negatif"}</span>
    </article>
  `).join("");
}

renderRoute();
