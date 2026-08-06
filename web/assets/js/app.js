"use strict";

/* ==========================================================================
   Carro da Liliana - Interactive Web Application Logic
   ========================================================================== */

// Global State
let flatCars = [];
let testDriveReviews = [];
let selectedCompareCars = [];

// Todo o valor do catálogo interpolado em innerHTML passa por aqui. Ver
// assets/js/html.js para o motivo.
const { escapeHtml } = VehicleHtml;
const {
  getPrice,
  getReferenceOffers,
  getFilterPrice,
  status: getPriceStatus,
} = VehiclePrices;

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  flattenCarData();
  setupNavigation();
  setupFilters();
  renderOverview(getFilteredCars());
  renderStands();
  populateDropdowns();
  setupComparator();
  setupTestDriveScores();
  loadSavedReviews();

  // Refresh button
  document.getElementById("btn-refresh-data").addEventListener("click", () => {
    location.reload();
  });
});

/* ==========================================================================
   Data Flattening Utility
   ========================================================================== */
function flattenCarData() {
  flatCars = [];

  if (typeof CAR_DATA === "undefined") {
    console.error("CAR_DATA is not defined. Ensure car_data.js is loaded.");
    return;
  }

  CAR_DATA.filter((car) => car.eligible !== false).forEach((car) => {
    const dim = car.dimensions || {};
    const lug = car.luggage_capacity || {};
    const variantCount = Array.isArray(car.variants) ? car.variants.length : 1;
    const isSingleVariant = variantCount === 1;

    // Check if the car model has multiple variants
    if (car.variants && Array.isArray(car.variants)) {
      car.variants.forEach((v) => {
        const vDim = v.dimensions || {};
        const vLug = v.luggage_capacity || {};

        const bootL =
          lug.boot_capacity_l ??
          vLug.boot_capacity_l ??
          car.specifications_common?.trunk_capacity_l ??
          v.trunk_capacity_l ??
          null;
        const frunkL =
          lug.frunk_capacity_l ??
          vLug.frunk_capacity_l ??
          car.specifications_common?.frunk_capacity_l ??
          v.frunk_capacity_l ??
          null;

        flatCars.push({
          id: `${car.brand}-${car.model}-${v.name}`
            .replace(/\s+/g, "-")
            .toLowerCase(),
          brand: car.brand,
          model: car.model,
          variant: v.name,
          is_single_variant: isSingleVariant,
          variant_count: variantCount,
          segment: car.segment,
          dimensions: {
            length_mm: dim.length_mm || vDim.length_mm || null,
            width_mm: dim.width_mm || vDim.width_mm || null,
            height_mm: dim.height_mm || vDim.height_mm || null,
            wheelbase_mm: dim.wheelbase_mm || vDim.wheelbase_mm || null,
            turning_radius_m:
              car.specifications_common?.turning_radius_m || null,
          },
          luggage_capacity: {
            boot_capacity_l: bootL,
            frunk_capacity_l: frunkL,
          },
          specifications: {
            battery_type:
              v.battery_technology?.chemistry ||
              car.specifications_common?.battery_type ||
              null,
            battery_capacity_kwh: v.battery_capacity_kwh,
            wltp_range_combined_km: v.wltp_range_combined_km,
            wltp_range_urban_km: v.wltp_range_urban_km || null,
            wltp_consumption_combined_kwh_100km:
              v.wltp_consumption_combined_kwh_100km,
            fuel_consumption_l_100km: v.fuel_consumption_l_100km || null,
            power_hp: v.power_hp,
            power_kw: v.power_kw,
            torque_nm: v.torque_nm,
            acceleration_0_100_s: v.acceleration_0_100_s,
            max_speed_kmh: v.max_speed_kmh,
            drivetrain:
              v.drivetrain || car.specifications_common?.drivetrain || null,
            trunk_capacity_l: bootL,
            boot_capacity_l: bootL,
            frunk_capacity_l: frunkL,
          },
          charging: {
            ac_max_kw: v.ac_max_kw || null,
            ac_charge_time_0_100: v.ac_charge_time_0_100 || "N/A",
            dc_max_kw: v.dc_max_kw || null,
            dc_charge_time_30_80_min: v.dc_charge_time_30_80_min || null,
          },
          pricing: v.pricing || { offers: [] },
          proposals: car.proposals || [],
          features: car.features_trims || car.features || {},
          pros: car.pros || [],
          cons: car.cons || [],
          technology_advantages: {
            ...(car.technology_advantages || {}),
            battery_tech:
              v.battery_technology ||
              car.technology_advantages?.battery_tech ||
              null,
          },
          image_path: car.image_path || "",
          release_year: car.release_year || null,
          official_link: car.official_link || "",
          data_sources: car.data_sources || [],
          powertrain: car.powertrain,
          user_reviews: car.user_reviews || {},
        });
      });
    } else {
      // Single model
      const bootL =
        lug.boot_capacity_l ?? car.specifications?.trunk_capacity_l ?? null;
      const frunkL =
        lug.frunk_capacity_l ?? car.specifications?.frunk_capacity_l ?? null;

      flatCars.push({
        id: `${car.brand}-${car.model}-${car.variant}`
          .replace(/\s+/g, "-")
          .toLowerCase(),
        brand: car.brand,
        model: car.model,
        variant: car.variant,
        is_single_variant: isSingleVariant,
        variant_count: variantCount,
        segment: car.segment,
        dimensions: {
          length_mm: dim.length_mm || car.dimensions?.length_mm || null,
          width_mm: dim.width_mm || car.dimensions?.width_mm || null,
          height_mm: dim.height_mm || car.dimensions?.height_mm || null,
          wheelbase_mm:
            dim.wheelbase_mm || car.dimensions?.wheelbase_mm || null,
          turning_radius_m: car.specifications?.turning_radius_m || null,
        },
        luggage_capacity: {
          boot_capacity_l: bootL,
          frunk_capacity_l: frunkL,
        },
        specifications: {
          ...(car.specifications || {}),
          battery_type:
            car.specifications?.battery_type ||
            car.battery_technology?.chemistry ||
            null,
          trunk_capacity_l: bootL,
          boot_capacity_l: bootL,
          frunk_capacity_l: frunkL,
        },
        charging: car.charging || {},
        pricing: car.pricing || {},
        proposals: car.proposals || [],
        features: car.features || {},
        pros: car.pros || [],
        cons: car.cons || [],
        technology_advantages: {
          ...(car.technology_advantages || {}),
          battery_tech:
            car.battery_technology ||
            car.specifications?.battery_technology ||
            car.technology_advantages?.battery_tech ||
            null,
        },
        image_path: car.image_path || "",
        release_year: car.release_year || null,
        official_link: car.official_link || "",
        data_sources: car.data_sources || [],
        powertrain: car.powertrain,
        user_reviews: car.user_reviews || {},
      });
    }
  });
}

/* ==========================================================================
   Navigation Tabs Logic
   ========================================================================== */
function setupNavigation() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach((btn) => {
    const activateTab = () => {
      // Deactivate all
      tabBtns.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
        b.tabIndex = -1;
      });
      tabContents.forEach((c) => {
        c.classList.remove("active");
        c.hidden = true;
      });

      // Activate selected
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      btn.tabIndex = 0;
      const tabId = btn.getAttribute("data-tab");
      const panel = document.getElementById(tabId);
      panel.classList.add("active");
      panel.hidden = false;

      // Trigger updates depending on tab
      if (tabId === "tab-compare") {
        updateComparison();
      }
    };
    btn.addEventListener("click", activateTab);
    btn.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const buttons = [...tabBtns];
      const current = buttons.indexOf(btn);
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? buttons.length - 1
            : (current +
                (event.key === "ArrowRight" ? 1 : -1) +
                buttons.length) %
              buttons.length;
      buttons[next].focus();
      buttons[next].click();
    });
  });
}

/* ==========================================================================
   TAB: Overview Card Rendering
   ========================================================================== */
function priceSourceHTML(price) {
  const source = typeof price?.source === "string" ? price.source : "";
  const sourceLink = /^https:\/\//i.test(source)
    ? `<a href="${escapeHtml(source)}" target="_blank" rel="noopener noreferrer">Fonte</a>`
    : "Fonte por confirmar";
  const recorded = price?.recordedOn
    ? ` · registado ${escapeHtml(price.recordedOn)}`
    : "";
  return `${sourceLink}${recorded}`;
}

function priceStatusLabel(car) {
  const status = getPriceStatus(car);
  if (status === "confirmed_eligible")
    return "Preço confirmado c/ IVA — elegível";
  if (status === "potential_reference")
    return "Valor de referência — não elegível";
  return "Preço não demonstrado";
}

function overviewPriceLabel(price, confirmedPrice) {
  if (confirmedPrice) {
    return confirmedPrice.type === "campaign"
      ? "Campanha confirmada c/ IVA"
      : "Preço confirmado c/ IVA";
  }
  return price?.vat === "excluded"
    ? "Valor de referência — não é PVP · IVA não incluído"
    : "Valor de referência — não é PVP";
}

function renderOverview(filteredList = flatCars) {
  const container = document.getElementById("cars-overview-grid");
  if (!container) return;
  container.innerHTML = "";
  const count = document.getElementById("catalog-count");
  if (count) {
    const confirmedCount = filteredList.filter(
      (car) => getPriceStatus(car) === "confirmed_eligible",
    ).length;
    count.textContent = `${filteredList.length} variantes apresentadas · ${confirmedCount} com preço confirmado c/ IVA · ${flatCars.length} no catálogo BEV.`;
  }

  if (filteredList.length === 0) {
    container.innerHTML = `
      <div class="glass-panel empty-state">
        <i class="fa-solid fa-car-burst"></i>
        <h3>Nenhum carro encontrado</h3>
        <p>Tenta ajustar os filtros de pesquisa para veres mais opções.</p>
      </div>
    `;
    return;
  }

  filteredList.forEach((car) => {
    const card = document.createElement("article");
    card.className = `glass-panel car-card ${car.brand.toLowerCase()}-card`;

    // Formatted prices
    const confirmedPrice = getPrice(car);
    const referencePrice = getPrice(car, { allowReference: true });
    const displayPrice = confirmedPrice || referencePrice;
    let priceHTML = "";
    if (displayPrice) {
      priceHTML = `
        <div class="price-main">${formatCurrency(displayPrice.amount)}</div>
        <div class="price-sub"><span class="price-chip ${confirmedPrice ? "price-chip-confirmed" : "price-chip-reference"}">${overviewPriceLabel(displayPrice, confirmedPrice)}</span></div>
        <div class="price-meta">${priceSourceHTML(displayPrice)}</div>
      `;
    } else {
      priceHTML = `
        <div class="price-main price-main--muted">Sob consulta</div>
        <div class="price-sub">Campanha Lançamento</div>
      `;
    }

    // Specs
    const range = car.specifications.wltp_range_combined_km
      ? `${car.specifications.wltp_range_combined_km} km`
      : car.specifications.wltp_range_urban_km
        ? `${car.specifications.wltp_range_urban_km} km (Urb)`
        : "N/A";

    const battery = car.specifications.battery_capacity_kwh
      ? `${car.specifications.battery_capacity_kwh} kWh`
      : "N/A";

    const power = car.specifications.power_hp
      ? `${car.specifications.power_hp} cv`
      : "N/A";

    // Dimensions & Luggage formatting
    const dim = car.dimensions;
    const dimensionsText =
      dim && dim.length_mm && dim.width_mm && dim.height_mm
        ? `${escapeHtml(dim.length_mm)} × ${escapeHtml(dim.width_mm)} × ${escapeHtml(dim.height_mm)} mm`
        : "N/A";

    const bootL =
      car.specifications.boot_capacity_l ||
      car.specifications.trunk_capacity_l ||
      (car.luggage_capacity && car.luggage_capacity.boot_capacity_l);
    const frunkL =
      car.specifications.frunk_capacity_l !== undefined
        ? car.specifications.frunk_capacity_l
        : car.luggage_capacity && car.luggage_capacity.frunk_capacity_l;
    let luggageText = "N/A";
    if (bootL && frunkL) {
      luggageText = `Mala: ${escapeHtml(bootL)} L (+ ${escapeHtml(frunkL)} L frunk)`;
    } else if (bootL) {
      luggageText = `Mala: ${escapeHtml(bootL)} L`;
    } else if (frunkL) {
      luggageText = `Frunk: ${escapeHtml(frunkL)} L`;
    }

    // Pros & Cons
    const prosHTML = car.pros
      .map(
        (pro) =>
          `<div class="pro-item"><i class="fa-solid fa-check"></i> <span>${escapeHtml(pro)}</span></div>`,
      )
      .join("");
    const consHTML = car.cons
      .map(
        (con) =>
          `<div class="con-item"><i class="fa-solid fa-xmark"></i> <span>${escapeHtml(con)}</span></div>`,
      )
      .join("");

    const imagePath = car.image_path || "";
    const imageHTML = imagePath
      ? `<img src="${escapeHtml(imagePath)}" alt="${escapeHtml(`${car.brand} ${car.model}`)}" class="card-car-image" loading="lazy" decoding="async" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
         <div class="card-image-fallback" style="display: none;"><i class="fa-solid fa-car"></i></div>`
      : `<div class="card-image-fallback" style="display: flex;"><i class="fa-solid fa-car"></i></div>`;

    let officialLinkHTML = "";
    if (car.official_link) {
      officialLinkHTML = `
        <a href="${escapeHtml(car.official_link)}" target="_blank" rel="noopener noreferrer" class="card-official-link">
          <i class="fa-solid fa-arrow-up-right-from-square"></i> Website Oficial (PT)
        </a>
      `;
    }

    const dealer =
      typeof DEALER_DATA !== "undefined" ? DEALER_DATA[car.brand] : null;
    const dealerLinkHTML = dealer
      ? `
      <a href="${escapeHtml(dealer.maps_url)}" target="_blank" rel="noopener noreferrer" class="card-official-link dealer-link">
        <i class="fa-solid fa-location-dot"></i> Concessionário mais próximo: ${escapeHtml(dealer.name)}
      </a>
    `
      : "";

    let userReviewHTML = "";
    if (car.user_reviews && car.user_reviews.score) {
      let starsHTML = "";
      const roundedAvg = Math.round(car.user_reviews.score);
      for (let i = 1; i <= 5; i++) {
        if (i <= roundedAvg) {
          starsHTML +=
            "<i class='fa-solid fa-star' style='color: #fbbf24; font-size: 0.8rem; margin-right: 1px;'></i>";
        } else {
          starsHTML +=
            "<i class='fa-regular fa-star' style='color: #d1d5db; font-size: 0.8rem; margin-right: 1px;'></i>";
        }
      }
      userReviewHTML = `
        <div class="card-user-reviews">
          <span style="display: flex;">${starsHTML}</span>
          <span style="font-weight: 700; color: #fbbf24;">${car.user_reviews.score.toFixed(1)}</span>
          <span style="color: var(--text-muted); font-size: 0.75rem;">(${escapeHtml(car.user_reviews.total_reviews)} avaliações • ${escapeHtml(car.user_reviews.source)})</span>
        </div>
      `;
    } else {
      userReviewHTML = `
        <div class="card-user-reviews">
          <span style="color: var(--text-muted); font-size: 0.75rem;"><i class="fa-solid fa-star-half-stroke"></i> Sem avaliações de utilizadores</span>
        </div>
      `;
    }

    // Micro Badges
    let badgesHTML = "";
    if (car.is_single_variant) {
      badgesHTML += `<span class="card-badge badge-single-variant"><i class="fa-solid fa-layer-group"></i> Variante única</span>`;
    }
    if (confirmedPrice && confirmedPrice.amount <= 25000) {
      badgesHTML += `<span class="card-badge badge-budget"><i class="fa-solid fa-piggy-bank"></i> ≤ 25k €</span>`;
    }
    if (
      car.specifications.wltp_range_combined_km &&
      car.specifications.wltp_range_combined_km >= 400
    ) {
      badgesHTML += `<span class="card-badge badge-range"><i class="fa-solid fa-route"></i> 400+ km</span>`;
    }
    if (car.charging.dc_max_kw && car.charging.dc_max_kw >= 100) {
      badgesHTML += `<span class="card-badge badge-fast-charge"><i class="fa-solid fa-bolt"></i> DC ${car.charging.dc_max_kw} kW</span>`;
    }
    if (confirmedPrice?.type === "campaign") {
      badgesHTML += `<span class="card-badge badge-campaign"><i class="fa-solid fa-tag"></i> Campanha</span>`;
    }

    const isSelected = selectedCompareCars.some((c) => c.id === car.id);
    const compareBtnHTML = `
      <button class="btn-compare-card ${isSelected ? "selected" : ""}" data-car-id="${escapeHtml(car.id)}">
        <i class="fa-solid ${isSelected ? "fa-check" : "fa-plus"}"></i> ${isSelected ? "Selecionado para Comparar" : "Adicionar à Comparação"}
      </button>
    `;

    card.innerHTML = `
      <div class="card-image-wrapper">
        ${imageHTML}
      </div>

      <div class="card-body-content">
        <div class="card-header">
          <span class="brand-badge brand-${escapeHtml(car.brand.toLowerCase())}">${escapeHtml(car.brand)}</span>
          <div class="car-price-tag">
            ${priceHTML}
          </div>
        </div>

        ${badgesHTML ? `<div class="card-badges">${badgesHTML}</div>` : ""}

        <h3 class="car-title">${escapeHtml(car.model)}</h3>
        <p class="car-segment">${escapeHtml(car.variant)} • ${escapeHtml(car.segment || "Segmento")} • 100% elétrico</p>
        ${userReviewHTML}

        <div class="card-quick-specs">
          <div class="quick-spec-item">
            <i class="fa-solid fa-bolt-lightning quick-spec-icon"></i>
            <span class="quick-spec-val">${battery}</span>
            <span class="quick-spec-lbl">Bateria</span>
          </div>
          <div class="quick-spec-item">
            <i class="fa-solid fa-gauge-high quick-spec-icon"></i>
            <span class="quick-spec-val">${range}</span>
            <span class="quick-spec-lbl">Autonomia</span>
          </div>
          <div class="quick-spec-item">
            <i class="fa-solid fa-horse-head quick-spec-icon"></i>
            <span class="quick-spec-val">${power}</span>
            <span class="quick-spec-lbl">Potência</span>
          </div>
        </div>
        <p class="battery-technology"><strong>Tecnologia da bateria:</strong> ${escapeHtml(car.specifications.battery_type || "Tecnologia por confirmar")}</p>

        <div class="card-dimensions-luggage">
          <div class="card-dimensions-info">
            <i class="fa-solid fa-ruler-combined"></i>
            <span><strong>Dimensões:</strong> ${dimensionsText}</span>
          </div>
          <div class="card-luggage-info">
            <i class="fa-solid fa-suitcase"></i>
            <span><strong>Bagageira:</strong> ${luggageText}</span>
          </div>
        </div>

        <div class="pros-cons-section">
          <div>
            <h4>Pontos Fortes</h4>
            <div class="pros-list">${prosHTML || "<p class='no-data-text'>Nenhum adicionado</p>"}</div>
          </div>
          <div class="cons-block">
            <h4>Pontos Fracos</h4>
            <div class="cons-list">${consHTML || "<p class='no-data-text'>Nenhum adicionado</p>"}</div>
          </div>
        </div>
        ${officialLinkHTML}
        ${dealerLinkHTML}
        ${compareBtnHTML}
      </div>
    `;

    const compareBtn = card.querySelector(".btn-compare-card");
    if (compareBtn) {
      compareBtn.addEventListener("click", () => toggleCompareCar(car));
    }

    container.appendChild(card);
  });
  updateCompareDrawer();
}

/* ==========================================================================
   TAB: Overview Filters Setup
   ========================================================================== */
function setupFilters() {
  const searchInput = document.getElementById("filter-search");
  const priceSlider = document.getElementById("filter-price");
  const rangeSlider = document.getElementById("filter-range");
  const batterySlider = document.getElementById("filter-battery");
  const yearSelect = document.getElementById("filter-year");
  const sortSelect = document.getElementById("filter-sort");
  const priceStatusSelect = document.getElementById("filter-price-status");
  const btnLilianaRules = document.getElementById("btn-liliana-rules");
  const btnClearFilters = document.getElementById("btn-clear-filters");

  const btnBudget = document.getElementById("btn-filter-budget");
  const btnRange = document.getElementById("btn-filter-range");
  const btnFastCharge = document.getElementById("btn-filter-fastcharge");

  const resetPresetClasses = () => {
    document
      .querySelectorAll(".preset-btn")
      .forEach((b) => b.classList.remove("active"));
  };

  if (searchInput)
    searchInput.addEventListener("input", () =>
      renderOverview(getFilteredCars()),
    );
  if (priceSlider)
    priceSlider.addEventListener("input", () =>
      renderOverview(getFilteredCars()),
    );
  if (rangeSlider)
    rangeSlider.addEventListener("input", () =>
      renderOverview(getFilteredCars()),
    );
  if (batterySlider)
    batterySlider.addEventListener("input", () =>
      renderOverview(getFilteredCars()),
    );
  if (yearSelect)
    yearSelect.addEventListener("change", () =>
      renderOverview(getFilteredCars()),
    );
  if (sortSelect)
    sortSelect.addEventListener("change", () =>
      renderOverview(getFilteredCars()),
    );
  if (priceStatusSelect)
    priceStatusSelect.addEventListener("change", () =>
      renderOverview(getFilteredCars()),
    );

  if (btnLilianaRules) {
    btnLilianaRules.addEventListener("click", () => {
      resetPresetClasses();
      btnLilianaRules.classList.add("active");
      if (priceSlider) priceSlider.value = "35000";
      if (rangeSlider) rangeSlider.value = "300";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  if (btnBudget) {
    btnBudget.addEventListener("click", () => {
      resetPresetClasses();
      btnBudget.classList.add("active");
      if (priceSlider) priceSlider.value = "25000";
      if (rangeSlider) rangeSlider.value = "80";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  if (btnRange) {
    btnRange.addEventListener("click", () => {
      resetPresetClasses();
      btnRange.classList.add("active");
      if (priceSlider) priceSlider.value = "40000";
      if (rangeSlider) rangeSlider.value = "400";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  if (btnFastCharge) {
    btnFastCharge.addEventListener("click", () => {
      resetPresetClasses();
      btnFastCharge.classList.add("active");
      if (priceSlider) priceSlider.value = "40000";
      if (rangeSlider) rangeSlider.value = "80";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  if (btnClearFilters) {
    btnClearFilters.addEventListener("click", () => {
      resetPresetClasses();
      btnClearFilters.classList.add("active");
      if (priceSlider) priceSlider.value = "40000";
      if (rangeSlider) rangeSlider.value = "80";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  // Floating Compare Drawer button click
  const btnOpenDrawerCompare = document.getElementById(
    "btn-open-drawer-compare",
  );
  if (btnOpenDrawerCompare) {
    btnOpenDrawerCompare.addEventListener("click", () => {
      if (selectedCompareCars.length > 0) {
        const selectA = document.getElementById("comp-select-1");
        const selectB = document.getElementById("comp-select-2");
        if (selectA && selectedCompareCars[0])
          selectA.value = selectedCompareCars[0].id;
        if (selectB && selectedCompareCars[1])
          selectB.value = selectedCompareCars[1].id;
        const navCompare = document.getElementById("nav-compare");
        if (navCompare) navCompare.click();
      }
    });
  }

  // Run initial calculation to update labels
  getFilteredCars();
}

/* ==========================================================================
   Floating Comparison Drawer Helpers
   ========================================================================== */
function toggleCompareCar(car) {
  const index = selectedCompareCars.findIndex((c) => c.id === car.id);
  if (index >= 0) {
    selectedCompareCars.splice(index, 1);
  } else {
    if (selectedCompareCars.length >= 3) {
      alert("Podes selecionar até 3 carros em simultâneo para comparar.");
      return;
    }
    selectedCompareCars.push(car);
  }
  renderOverview(getFilteredCars());
}

function updateCompareDrawer() {
  const drawer = document.getElementById("floating-compare-drawer");
  const countEl = document.getElementById("compare-count");
  const chipsEl = document.getElementById("drawer-chips");
  if (!drawer || !countEl || !chipsEl) return;

  countEl.textContent = selectedCompareCars.length;
  if (selectedCompareCars.length === 0) {
    drawer.classList.remove("visible");
  } else {
    drawer.classList.add("visible");
    chipsEl.innerHTML = selectedCompareCars
      .map(
        (c) => `
      <div class="drawer-chip">
        <span>${escapeHtml(c.brand)} ${escapeHtml(c.model)}</span>
        <i class="fa-solid fa-xmark remove-chip" data-id="${escapeHtml(c.id)}"></i>
      </div>
    `,
      )
      .join("");

    chipsEl.querySelectorAll(".remove-chip").forEach((icon) => {
      icon.addEventListener("click", (e) => {
        const id = e.target.getAttribute("data-id");
        selectedCompareCars = selectedCompareCars.filter((c) => c.id !== id);
        renderOverview(getFilteredCars());
      });
    });
  }
}

function getFilteredCars() {
  const searchInput = document.getElementById("filter-search");
  const priceSlider = document.getElementById("filter-price");
  const rangeSlider = document.getElementById("filter-range");
  const batterySlider = document.getElementById("filter-battery");
  const yearSelect = document.getElementById("filter-year");
  const sortSelect = document.getElementById("filter-sort");
  const priceStatusSelect = document.getElementById("filter-price-status");

  const searchVal = searchInput ? searchInput.value : "";
  const maxPriceVal = priceSlider ? parseFloat(priceSlider.value) : 40000;
  const minRangeVal = rangeSlider ? parseFloat(rangeSlider.value) : 80;
  const minBatteryVal = batterySlider ? parseFloat(batterySlider.value) : 0;
  const yearVal = yearSelect ? yearSelect.value : "all";
  const sortVal = sortSelect ? sortSelect.value : "default";
  const priceStatusVal = priceStatusSelect ? priceStatusSelect.value : "all";

  // Update labels
  const priceDisplay = document.getElementById("filter-price-val");
  const priceNote = document.getElementById("filter-price-note");
  const rangeDisplay = document.getElementById("filter-range-val");

  if (priceDisplay) {
    if (maxPriceVal >= 40000) {
      priceDisplay.textContent = "Qualquer";
    } else {
      priceDisplay.textContent = formatCurrency(maxPriceVal);
    }
  }
  if (priceNote) {
    const usesReferenceCap =
      maxPriceVal < 40000 &&
      (priceStatusVal === "all" || priceStatusVal === "potential_reference") &&
      flatCars.some((car) => getPriceStatus(car) === "potential_reference");
    priceNote.textContent = usesReferenceCap
      ? "O limite inclui valores de referência; não são PVP confirmado nem elegibilidade."
      : "";
  }

  if (rangeDisplay) {
    if (minRangeVal <= 80) {
      rangeDisplay.textContent = "Qualquer";
    } else {
      rangeDisplay.textContent = `>= ${minRangeVal} km`;
    }
  }
  const batteryDisplay = document.getElementById("filter-battery-val");
  if (batteryDisplay)
    batteryDisplay.textContent =
      minBatteryVal > 0 ? `≥ ${minBatteryVal} kWh` : "Qualquer";

  const filtered = flatCars.filter((car) => {
    // Search filter
    const matchesSearch = VehicleSearch.matchesVehicleSearch(car, searchVal);

    // O teto usa coorte confirmada ou referência conforme estado selecionado.
    const price = getFilterPrice(car, priceStatusVal);
    const matchesPrice =
      maxPriceVal >= 40000
        ? true
        : Boolean(price && price.amount <= maxPriceVal);

    // Autonomy filter
    const range =
      car.specifications.wltp_range_combined_km ||
      car.specifications.wltp_range_urban_km ||
      0;
    const matchesRange = minRangeVal <= 80 || range >= minRangeVal;
    const battery = car.specifications.battery_capacity_kwh || 0;
    const matchesBattery = minBatteryVal <= 0 || battery >= minBatteryVal;
    const matchesPriceStatus =
      priceStatusVal === "all" || getPriceStatus(car) === priceStatusVal;

    // Release year filter
    let matchesYear = true;
    if (yearVal !== "all") {
      const minYear = parseInt(yearVal);
      matchesYear = car.release_year && car.release_year >= minYear;
    }

    return (
      matchesSearch &&
      matchesPrice &&
      matchesRange &&
      matchesBattery &&
      matchesPriceStatus &&
      matchesYear
    );
  });

  // Apply sorting
  if (sortVal === "price-asc") {
    filtered.sort((a, b) => {
      const pA = getPrice(a)?.amount ?? Infinity;
      const pB = getPrice(b)?.amount ?? Infinity;
      return pA - pB;
    });
  } else if (sortVal === "price-desc") {
    filtered.sort((a, b) => {
      const pA = getPrice(a)?.amount ?? -Infinity;
      const pB = getPrice(b)?.amount ?? -Infinity;
      return pB - pA;
    });
  } else if (sortVal === "range-desc") {
    filtered.sort((a, b) => {
      const rA = a.specifications.wltp_range_combined_km || 0;
      const rB = b.specifications.wltp_range_combined_km || 0;
      return rB - rA;
    });
  } else if (sortVal === "rating-desc") {
    filtered.sort((a, b) => {
      const rA = a.user_reviews?.score || 0;
      const rB = b.user_reviews?.score || 0;
      return rB - rA;
    });
  } else if (sortVal === "year-desc") {
    filtered.sort((a, b) => {
      const yA = a.release_year || 0;
      const yB = b.release_year || 0;
      return yB - yA;
    });
  } else {
    // Melhor preço/autonomia: 45% preço, 45% autonomia e 10% recência.
    filtered.sort((a, b) => {
      return (
        VehicleRanking.getPriceRangeScore(b) -
        VehicleRanking.getPriceRangeScore(a)
      );
    });
  }

  return filtered;
}

/* ==========================================================================
   Dropdowns Population
   ========================================================================== */
function populateDropdowns() {
  const compSelect1 = document.getElementById("comp-select-1");
  const compSelect2 = document.getElementById("comp-select-2");
  const tdSelectModel = document.getElementById("td-select-model");

  const selects = [compSelect1, compSelect2, tdSelectModel];

  selects.forEach((select) => {
    if (!select) return;
    select.innerHTML = "";

    flatCars.forEach((car) => {
      const option = document.createElement("option");
      option.value = car.id;
      option.textContent = `${car.brand} ${car.model} (${car.variant})`;
      select.appendChild(option);
    });
  });

  // Set defaults
  if (compSelect1 && compSelect2 && flatCars.length >= 2) {
    // Defaults: first two confirmed_eligible cars, or fall back to first two.
    const best = flatCars.filter(
      (c) => getPriceStatus(c) === "confirmed_eligible",
    );
    const fallback = best.length >= 2 ? best : flatCars;
    compSelect1.value = fallback[0]?.id || "";
    compSelect2.value = fallback[1]?.id || fallback[0]?.id || "";
  }
}

/* ==========================================================================
   TAB: Technical Comparator Logic
   ========================================================================== */
function setupComparator() {
  const compSelect1 = document.getElementById("comp-select-1");
  const compSelect2 = document.getElementById("comp-select-2");

  if (compSelect1) compSelect1.addEventListener("change", updateComparison);
  if (compSelect2) compSelect2.addEventListener("change", updateComparison);
}

function updateComparison() {
  const idA = document.getElementById("comp-select-1").value;
  const idB = document.getElementById("comp-select-2").value;

  const carA = flatCars.find((c) => c.id === idA);
  const carB = flatCars.find((c) => c.id === idB);

  if (!carA || !carB) return;

  // Update titles
  document.getElementById("th-car-a").textContent =
    `${carA.brand} ${carA.model} (${carA.variant})`;
  document.getElementById("th-car-b").textContent =
    `${carB.brand} ${carB.model} (${carB.variant})`;

  // 1. Comparison Bars
  // Max values for scaling
  const maxRange = 500;
  const maxAccel = 13;
  const maxBattery = 80;
  const maxTrunk = 500;

  // Range Combined
  const valRangeA = carA.specifications.wltp_range_combined_km || 0;
  const valRangeB = carB.specifications.wltp_range_combined_km || 0;
  document.getElementById("val-range-a").textContent = valRangeA
    ? `${valRangeA} km`
    : "N/A";
  document.getElementById("val-range-b").textContent = valRangeB
    ? `${valRangeB} km`
    : "N/A";
  document.getElementById("bar-range-a").style.width =
    `${Math.min(100, (valRangeA / maxRange) * 100)}%`;
  document.getElementById("bar-range-b").style.width =
    `${Math.min(100, (valRangeB / maxRange) * 100)}%`;

  // Accel (inverse: lower is better, but bar size represents speed)
  const valAccelA = carA.specifications.acceleration_0_100_s || 0;
  const valAccelB = carB.specifications.acceleration_0_100_s || 0;
  document.getElementById("val-accel-a").textContent = valAccelA
    ? `${valAccelA}s`
    : "N/A";
  document.getElementById("val-accel-b").textContent = valAccelB
    ? `${valAccelB}s`
    : "N/A";

  // Higher performance (lower 0-100 time) fills more bar
  const pctAccelA = valAccelA
    ? ((maxAccel - valAccelA) / (maxAccel - 5)) * 100
    : 0;
  const pctAccelB = valAccelB
    ? ((maxAccel - valAccelB) / (maxAccel - 5)) * 100
    : 0;
  document.getElementById("bar-accel-a").style.width =
    `${Math.max(5, Math.min(100, pctAccelA))}%`;
  document.getElementById("bar-accel-b").style.width =
    `${Math.max(5, Math.min(100, pctAccelB))}%`;

  // Battery
  const valBatteryA = carA.specifications.battery_capacity_kwh || 0;
  const valBatteryB = carB.specifications.battery_capacity_kwh || 0;
  document.getElementById("val-battery-a").textContent = valBatteryA
    ? `${valBatteryA} kWh`
    : "N/A";
  document.getElementById("val-battery-b").textContent = valBatteryB
    ? `${valBatteryB} kWh`
    : "N/A";
  document.getElementById("bar-battery-a").style.width =
    `${Math.min(100, (valBatteryA / maxBattery) * 100)}%`;
  document.getElementById("bar-battery-b").style.width =
    `${Math.min(100, (valBatteryB / maxBattery) * 100)}%`;

  // Trunk
  const valTrunkA = carA.specifications.trunk_capacity_l || 0;
  const valTrunkB = carB.specifications.trunk_capacity_l || 0;
  document.getElementById("val-trunk-a").textContent = valTrunkA
    ? `${valTrunkA} L`
    : "N/A";
  document.getElementById("val-trunk-b").textContent = valTrunkB
    ? `${valTrunkB} L`
    : "N/A";
  document.getElementById("bar-trunk-a").style.width =
    `${Math.min(100, (valTrunkA / maxTrunk) * 100)}%`;
  document.getElementById("bar-trunk-b").style.width =
    `${Math.min(100, (valTrunkB / maxTrunk) * 100)}%`;

  // 2. Comparison Table
  const tbody = document.getElementById("tech-comparison-tbody");
  tbody.innerHTML = "";

  const priceA = getPrice(carA);
  const priceB = getPrice(carB);

  const { boolLabel, v2lLabel, cellValue } = VehicleSpecs;

  const rows = [
    { label: "Marca", valA: carA.brand, valB: carB.brand },
    { label: "Modelo", valA: carA.model, valB: carB.model },
    { label: "Equipamento", valA: carA.variant, valB: carB.variant },
    {
      label: "Estado desta variante",
      valA: priceStatusLabel(carA),
      valB: priceStatusLabel(carB),
    },
    {
      label: "Preço confirmado c/ IVA",
      valA: priceA ? formatCurrency(priceA.amount) : "Não demonstrado",
      valB: priceB ? formatCurrency(priceB.amount) : "Não demonstrado",
      highlight: true,
    },
    {
      label: "Avaliação Utilizadores",
      valA: carA.user_reviews?.score
        ? `${carA.user_reviews.score.toFixed(1)} / 5 (${carA.user_reviews.total_reviews} avaliações • ${carA.user_reviews.source})`
        : "N/D",
      valB: carB.user_reviews?.score
        ? `${carB.user_reviews.score.toFixed(1)} / 5 (${carB.user_reviews.total_reviews} avaliações • ${carB.user_reviews.source})`
        : "N/D",
      highlight: true,
    },
    {
      label: "Tecnologia da Bateria",
      valA: carA.specifications.battery_type || "Tecnologia por confirmar",
      valB: carB.specifications.battery_type || "Tecnologia por confirmar",
    },
    {
      label: "Química da Bateria",
      valA: carA.technology_advantages?.battery_tech?.chemistry || "N/A",
      valB: carB.technology_advantages?.battery_tech?.chemistry || "N/A",
    },
    {
      label: "Tecnologia Bateria",
      valA: carA.technology_advantages?.battery_tech?.generation || "N/A",
      valB: carB.technology_advantages?.battery_tech?.generation || "N/A",
    },
    {
      label: "Arquitetura Bateria",
      valA: carA.technology_advantages?.battery_tech?.architecture || "N/A",
      valB: carB.technology_advantages?.battery_tech?.architecture || "N/A",
    },
    {
      label: "Bomba de Calor Standard",
      valA: boolLabel(
        carA.technology_advantages?.battery_tech?.heat_pump_included,
      ),
      valB: boolLabel(
        carB.technology_advantages?.battery_tech?.heat_pump_included,
      ),
    },
    {
      label: "Pré-aquecimento Bateria",
      valA: boolLabel(
        carA.technology_advantages?.battery_tech?.battery_preheating,
      ),
      valB: boolLabel(
        carB.technology_advantages?.battery_tech?.battery_preheating,
      ),
    },
    {
      label: "Carregamento Bidirecional V2L",
      valA: v2lLabel(carA),
      valB: v2lLabel(carB),
      highlight: true,
    },
    {
      label: "Capacidade Bateria (kWh)",
      valA: carA.specifications.battery_capacity_kwh,
      valB: carB.specifications.battery_capacity_kwh,
    },
    {
      label: "Autonomia WLTP Mista (km)",
      valA: carA.specifications.wltp_range_combined_km
        ? `${carA.specifications.wltp_range_combined_km} km`
        : "N/A",
      valB: carB.specifications.wltp_range_combined_km
        ? `${carB.specifications.wltp_range_combined_km} km`
        : "N/A",
      highlight: true,
    },
    {
      label: "Autonomia WLTP Urbana (km)",
      valA: carA.specifications.wltp_range_urban_km
        ? `${carA.specifications.wltp_range_urban_km} km`
        : "N/A",
      valB: carB.specifications.wltp_range_urban_km
        ? `${carB.specifications.wltp_range_urban_km} km`
        : "N/A",
    },
    {
      label: "Consumo Misto (kWh/100km)",
      valA: carA.specifications.wltp_consumption_combined_kwh_100km
        ? `${carA.specifications.wltp_consumption_combined_kwh_100km} kWh`
        : "N/A",
      valB: carB.specifications.wltp_consumption_combined_kwh_100km
        ? `${carB.specifications.wltp_consumption_combined_kwh_100km} kWh`
        : "N/A",
    },
    {
      label: "Potência Máxima",
      valA: carA.specifications.power_hp
        ? `${carA.specifications.power_hp} cv (${carA.specifications.power_kw} kW)`
        : "N/A",
      valB: carB.specifications.power_hp
        ? `${carB.specifications.power_hp} cv (${carB.specifications.power_kw} kW)`
        : "N/A",
    },
    {
      label: "Binário Motor",
      valA: carA.specifications.torque_nm
        ? `${carA.specifications.torque_nm} Nm`
        : "N/A",
      valB: carB.specifications.torque_nm
        ? `${carB.specifications.torque_nm} Nm`
        : "N/A",
    },
    {
      label: "Aceleração 0-100 km/h",
      valA: carA.specifications.acceleration_0_100_s
        ? `${carA.specifications.acceleration_0_100_s} seg`
        : "N/A",
      valB: carB.specifications.acceleration_0_100_s
        ? `${carB.specifications.acceleration_0_100_s} seg`
        : "N/A",
      highlight: true,
    },
    {
      label: "Tração",
      valA: carA.specifications.drivetrain || "N/A",
      valB: carB.specifications.drivetrain || "N/A",
    },
    {
      label: "Suspensão Traseira",
      valA: carA.specifications.suspension_rear || "N/A",
      valB: carB.specifications.suspension_rear || "N/A",
    },
    {
      label: "Capacidade Bagageira",
      valA: carA.specifications.trunk_capacity_l
        ? `${carA.specifications.trunk_capacity_l} L`
        : "N/A",
      valB: carB.specifications.trunk_capacity_l
        ? `${carB.specifications.trunk_capacity_l} L`
        : "N/A",
    },
    {
      label: "Frunk (Bagageira Dianteira)",
      valA:
        carA.specifications.frunk_capacity_l !== null &&
        carA.specifications.frunk_capacity_l !== undefined
          ? `${carA.specifications.frunk_capacity_l} L`
          : "Não / N/A",
      valB:
        carB.specifications.frunk_capacity_l !== null &&
        carB.specifications.frunk_capacity_l !== undefined
          ? `${carB.specifications.frunk_capacity_l} L`
          : "Não / N/A",
    },
    {
      label: "Dimensões (C × L × A)",
      valA:
        carA.dimensions?.length_mm &&
        carA.dimensions?.width_mm &&
        carA.dimensions?.height_mm
          ? `${carA.dimensions.length_mm} × ${carA.dimensions.width_mm} × ${carA.dimensions.height_mm} mm`
          : "N/A",
      valB:
        carB.dimensions?.length_mm &&
        carB.dimensions?.width_mm &&
        carB.dimensions?.height_mm
          ? `${carB.dimensions.length_mm} × ${carB.dimensions.width_mm} × ${carB.dimensions.height_mm} mm`
          : "N/A",
      highlight: true,
    },
    {
      label: "Comprimento Exterior",
      valA: carA.dimensions?.length_mm
        ? `${carA.dimensions.length_mm / 1000} m`
        : "N/A",
      valB: carB.dimensions?.length_mm
        ? `${carB.dimensions.length_mm / 1000} m`
        : "N/A",
    },
    {
      label: "Largura Exterior",
      valA: carA.dimensions?.width_mm
        ? `${carA.dimensions.width_mm / 1000} m`
        : "N/A",
      valB: carB.dimensions?.width_mm
        ? `${carB.dimensions.width_mm / 1000} m`
        : "N/A",
    },
    {
      label: "Altura Exterior",
      valA: carA.dimensions?.height_mm
        ? `${carA.dimensions.height_mm / 1000} m`
        : "N/A",
      valB: carB.dimensions?.height_mm
        ? `${carB.dimensions.height_mm / 1000} m`
        : "N/A",
    },
    {
      label: "Distância entre Eixos",
      valA: carA.dimensions?.wheelbase_mm
        ? `${carA.dimensions.wheelbase_mm} mm`
        : "N/A",
      valB: carB.dimensions?.wheelbase_mm
        ? `${carB.dimensions.wheelbase_mm} mm`
        : "N/A",
    },
    {
      label: "Raio de Viragem",
      valA: carA.dimensions?.turning_radius_m
        ? `${carA.dimensions.turning_radius_m} m`
        : "N/A",
      valB: carB.dimensions?.turning_radius_m
        ? `${carB.dimensions.turning_radius_m} m`
        : "N/A",
    },
    {
      label: "Potência Máxima DC",
      valA: carA.charging.dc_max_kw ? `${carA.charging.dc_max_kw} kW` : "N/A",
      valB: carB.charging.dc_max_kw ? `${carB.charging.dc_max_kw} kW` : "N/A",
    },
    {
      label: "Carregamento DC 30-80%",
      valA: carA.charging.dc_charge_time_30_80_min
        ? `${carA.charging.dc_charge_time_30_80_min} min`
        : "N/A",
      valB: carB.charging.dc_charge_time_30_80_min
        ? `${carB.charging.dc_charge_time_30_80_min} min`
        : "N/A",
      highlight: true,
    },
    {
      label: "Processador Infotainment",
      valA: carA.technology_advantages?.infotainment_tech?.processor || "N/A",
      valB: carB.technology_advantages?.infotainment_tech?.processor || "N/A",
    },
    {
      label: "Google Built-in",
      valA: boolLabel(
        carA.technology_advantages?.infotainment_tech?.google_built_in,
      ),
      valB: boolLabel(
        carB.technology_advantages?.infotainment_tech?.google_built_in,
      ),
    },
    {
      label: "Atualizações OTA",
      valA: boolLabel(
        carA.technology_advantages?.infotainment_tech?.ota_updates,
      ),
      valB: boolLabel(
        carB.technology_advantages?.infotainment_tech?.ota_updates,
      ),
    },
    {
      label: "Pontos Fortes (Pros)",
      valA: carA.pros && carA.pros.length ? carA.pros.join(" • ") : "N/A",
      valB: carB.pros && carB.pros.length ? carB.pros.join(" • ") : "N/A",
    },
    {
      label: "Pontos Fracos (Cons)",
      valA: carA.cons && carA.cons.length ? carA.cons.join(" • ") : "N/A",
      valB: carB.cons && carB.cons.length ? carB.cons.join(" • ") : "N/A",
    },
  ];

  rows.forEach((r) => {
    const tr = document.createElement("tr");

    const tdLabel = document.createElement("td");
    tdLabel.className = "cat-label";
    tdLabel.textContent = r.label;
    tr.appendChild(tdLabel);

    const tdValA = document.createElement("td");
    tdValA.className = r.highlight ? "val-highlight accent-color" : "";
    tdValA.textContent = cellValue(r.valA);
    tr.appendChild(tdValA);

    const tdValB = document.createElement("td");
    tdValB.className = r.highlight ? "val-highlight" : "";
    tdValB.style.color = r.highlight ? "var(--accent-purple)" : "";
    tdValB.textContent = cellValue(r.valB);
    tr.appendChild(tdValB);

    tbody.appendChild(tr);
  });

  const summary = document.getElementById("comparison-summary");
  if (summary) summary.innerHTML = comparisonOutcome(carA, carB);
}

function comparisonOutcome(carA, carB) {
  const metrics = [
    [
      "Autonomia",
      carA.specifications.wltp_range_combined_km,
      carB.specifications.wltp_range_combined_km,
      "maior",
    ],
    [
      "Bateria",
      carA.specifications.battery_capacity_kwh,
      carB.specifications.battery_capacity_kwh,
      "maior",
    ],
    [
      "Bagageira",
      carA.specifications.trunk_capacity_l,
      carB.specifications.trunk_capacity_l,
      "maior",
    ],
    [
      "Aceleração",
      carA.specifications.acceleration_0_100_s,
      carB.specifications.acceleration_0_100_s,
      "menor",
    ],
  ];
  const lines = metrics
    .map(([label, a, b, preference]) => {
      if (!a || !b || a === b)
        return `<li><strong>${escapeHtml(label)}:</strong> sem vencedor demonstrado.</li>`;
      const winner =
        preference === "menor" ? (a < b ? "A" : "B") : a > b ? "A" : "B";
      return `<li><strong>${escapeHtml(label)}:</strong> Carro ${winner} é melhor (${preference} valor).</li>`;
    })
    .join("");
  return `<div class="comparison-outcome"><strong>Leitura rápida</strong><ul>${lines}</ul></div>`;
}

/* ==========================================================================
   TAB: Test Drives Scoring & Persistency
   ========================================================================== */
function setupTestDriveScores() {
  const starsContainer = document.querySelectorAll(".stars-rating");
  starsContainer.forEach((container) => {
    const category = container.getAttribute("data-category");
    const stars = container.querySelectorAll(".star-btn");

    stars.forEach((star) => {
      // Hover highlight
      star.addEventListener("mouseenter", () => {
        const val = parseInt(star.getAttribute("data-value"));
        highlightStars(container, val);
      });

      star.addEventListener("mouseleave", () => {
        const currentRating = parseInt(
          container.getAttribute("data-rating") || "0",
        );
        highlightStars(container, currentRating);
      });

      // Click selection
      star.addEventListener("click", () => {
        const val = parseInt(star.getAttribute("data-value"));
        container.setAttribute("data-rating", val);
        highlightStars(container, val);
      });
    });
  });

  // Save button handler
  document
    .getElementById("btn-save-testdrive")
    .addEventListener("click", saveReview);
}

function highlightStars(container, rating) {
  const stars = container.querySelectorAll(".star-btn");
  stars.forEach((star) => {
    const val = parseInt(star.getAttribute("data-value"));
    const icon = star.querySelector("i");
    icon.className = val <= rating ? "fa-star fa-solid" : "fa-star fa-regular";
    star.setAttribute("aria-pressed", val <= rating ? "true" : "false");
  });
}

function saveReview() {
  const carId = document.getElementById("td-select-model").value;
  const car = flatCars.find((c) => c.id === carId);
  const notes = document.getElementById("td-input-notes").value.trim();

  if (!car) return;

  // Collect scores
  const scores = {};
  const categories = ["comfort", "space", "tech", "design", "value"];
  let totalScore = 0;

  categories.forEach((cat) => {
    const container = document.querySelector(
      `.stars-rating[data-category="${cat}"]`,
    );
    const rating = parseInt(container.getAttribute("data-rating") || "0");
    scores[cat] = rating;
    totalScore += rating;
  });

  const averageScore = totalScore / categories.length;

  if (totalScore === 0 && notes === "") {
    alert("Atribua algumas pontuações ou escreva notas antes de guardar!");
    return;
  }

  const newReview = {
    carId: car.id,
    carName: `${car.brand} ${car.model} (${car.variant})`,
    date: new Date().toLocaleDateString("pt-PT"),
    scores: scores,
    average: averageScore,
    notes: notes,
  };

  // Add to reviews list
  testDriveReviews = testDriveReviews.filter((r) => r.carId !== carId); // override previous review for this car
  testDriveReviews.unshift(newReview);

  // Save to LocalStorage
  localStorage.setItem(
    "carro_liliana_reviews",
    JSON.stringify(testDriveReviews),
  );

  // Reset form
  document.getElementById("td-input-notes").value = "";
  const starsContainers = document.querySelectorAll(".stars-rating");
  starsContainers.forEach((container) => {
    container.removeAttribute("data-rating");
    highlightStars(container, 0);
  });

  // Reload visual list
  renderReviewsList();
}

function loadSavedReviews() {
  const saved = localStorage.getItem("carro_liliana_reviews");
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      testDriveReviews = Array.isArray(parsed)
        ? parsed.filter(isValidReview)
        : [];
      renderReviewsList();
    } catch (e) {
      console.error("Error loading reviews", e);
    }
  }
}

function renderReviewsList() {
  const listContainer = document.getElementById("saved-reviews-list");
  if (!listContainer) return;

  if (testDriveReviews.length === 0) {
    listContainer.innerHTML =
      "<p class='no-data-text'>Sem avaliações registadas para já.</p>";
    return;
  }

  listContainer.innerHTML = "";
  testDriveReviews.forEach((review) => {
    const card = document.createElement("div");
    card.className = "review-item-card";

    // Build user-controlled content with textContent to prevent stored XSS.
    const header = document.createElement("div");
    header.className = "review-card-header";
    const title = document.createElement("span");
    title.className = "review-card-title";
    title.textContent = review.carName;
    const stars = document.createElement("span");
    stars.className = "review-card-stars";
    const roundedAvg = Math.round(review.average);
    for (let i = 1; i <= 5; i++) {
      const icon = document.createElement("i");
      icon.className =
        i <= roundedAvg ? "fa-solid fa-star" : "fa-regular fa-star";
      icon.setAttribute("aria-hidden", "true");
      stars.appendChild(icon);
    }
    stars.appendChild(
      document.createTextNode(` (${review.average.toFixed(1)})`),
    );
    header.append(title, stars);
    const date = document.createElement("small");
    date.textContent = `Avaliado a ${review.date}`;
    const notes = document.createElement("div");
    notes.className = "review-card-notes";
    notes.textContent =
      review.notes || "Sem notas de texto, apenas pontuações.";
    const details = document.createElement("div");
    details.className = "review-score-details";
    details.textContent = `Conforto: ${review.scores.comfort}/5 · Espaço: ${review.scores.space}/5 · Tecnologia: ${review.scores.tech}/5 · Design: ${review.scores.design}/5 · Relação preço: ${review.scores.value}/5`;
    card.append(header, date, notes, details);
    listContainer.appendChild(card);
  });
}

function isValidReview(review) {
  if (
    !review ||
    typeof review !== "object" ||
    typeof review.carName !== "string" ||
    typeof review.notes !== "string" ||
    !Number.isFinite(review.average) ||
    !review.scores ||
    typeof review.scores !== "object"
  )
    return false;
  return ["comfort", "space", "tech", "design", "value"].every(
    (key) =>
      Number.isInteger(review.scores[key]) &&
      review.scores[key] >= 0 &&
      review.scores[key] <= 5,
  );
}

/* ==========================================================================
   Helper Formatting Functions
   ========================================================================== */
function formatCurrency(val) {
  if (val === null || val === undefined) return "";
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
}

function formatNumber(val) {
  if (val === null || val === undefined) return "";
  return new Intl.NumberFormat("pt-PT").format(val);
}

function renderStands() {
  const container = document.getElementById("dynamic-stands-list");
  if (!container) return;
  container.innerHTML = "";

  // Get list of unique brands present in our flatCars array
  const activeBrands = [...new Set(flatCars.map((car) => car.brand))];

  activeBrands.forEach((brand) => {
    const dealer =
      typeof DEALER_DATA !== "undefined" ? DEALER_DATA[brand] : null;
    if (!dealer) return;

    const standItem = document.createElement("div");
    standItem.className = "stand-item";

    standItem.innerHTML = `
      <div class="stand-badge brand-${escapeHtml(brand.toLowerCase())}">${escapeHtml(brand)}</div>
      <div class="stand-details">
        <h4>${escapeHtml(dealer.name)}</h4>
        <p><i class="fa-solid fa-map-location-dot"></i> ${escapeHtml(dealer.address)}, ${escapeHtml(dealer.postal_code)} ${escapeHtml(dealer.locality)}</p>
        ${dealer.email ? `<p><i class="fa-solid fa-envelope"></i> <a href="mailto:${escapeHtml(dealer.email)}" style="color: var(--text-secondary); text-decoration: none;">${escapeHtml(dealer.email)}</a></p>` : ""}
        <p><i class="fa-solid fa-phone"></i> <a href="tel:${escapeHtml(dealer.phone.replace(/\s+/g, ""))}" style="color: var(--text-secondary); text-decoration: none;">${escapeHtml(dealer.phone)}</a></p>
        <p><i class="fa-solid fa-route"></i> <a href="${escapeHtml(dealer.maps_url)}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-blue);">Como chegar</a> · <a href="${escapeHtml(dealer.official_url)}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-green);">Página oficial</a></p>
      </div>
    `;
    container.appendChild(standItem);
  });
}
