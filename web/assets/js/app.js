/* ==========================================================================
   Carro da Liliana - Interactive Web Application Logic
   ========================================================================== */

// Global State
let flatCars = [];
let testDriveReviews = [];

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  flattenCarData();
  setupNavigation();
  setupFilters();
  renderOverview(getFilteredCars());
  renderStands();
  populateDropdowns();
  setupComparator();
  setupFinanceSimulator();
  setupTCOSavings();
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

  CAR_DATA.filter(car => car.eligible !== false).forEach(car => {
    // Check if the car model has multiple variants
    if (car.variants && Array.isArray(car.variants)) {
      car.variants.forEach(v => {
        flatCars.push({
          id: `${car.brand}-${car.model}-${v.name}`.replace(/\s+/g, "-").toLowerCase(),
          brand: car.brand,
          model: car.model,
          variant: v.name,
          segment: car.segment,
          dimensions: {
            length_mm: car.dimensions?.length_mm || v.dimensions?.length_mm || null,
            width_mm: car.dimensions?.width_mm || v.dimensions?.width_mm || null,
            height_mm: car.dimensions?.height_mm || v.dimensions?.height_mm || null,
            wheelbase_mm: car.dimensions?.wheelbase_mm || v.dimensions?.wheelbase_mm || null,
            turning_radius_m: car.specifications_common?.turning_radius_m || null
          },
          specifications: {
            battery_type: car.specifications_common?.battery_type || "LFP",
            battery_capacity_kwh: v.battery_capacity_kwh,
            wltp_range_combined_km: v.wltp_range_combined_km,
            wltp_range_urban_km: v.wltp_range_urban_km || null,
            wltp_consumption_combined_kwh_100km: v.wltp_consumption_combined_kwh_100km,
            fuel_consumption_l_100km: v.fuel_consumption_l_100km || null,
            power_hp: v.power_hp,
            power_kw: v.power_kw,
            torque_nm: v.torque_nm,
            acceleration_0_100_s: v.acceleration_0_100_s,
            max_speed_kmh: v.max_speed_kmh,
            trunk_capacity_l: car.specifications_common?.trunk_capacity_l || null,
            frunk_capacity_l: car.specifications_common?.frunk_capacity_l || null
          },
          charging: {
            ac_max_kw: v.ac_max_kw || 11.0,
            ac_charge_time_0_100: v.ac_charge_time_0_100 || "N/A",
            dc_max_kw: v.dc_max_kw || 140.0,
            dc_charge_time_30_80_min: v.dc_charge_time_30_80_min || null
          },
          pricing: {
            particular_list_price_vat_incl: v.pricing?.particular_list_price_vat_incl || null,
            particular_campaign_price_vat_incl: v.pricing?.particular_campaign_price_vat_incl || null,
            company_campaign_price_vat_excl: v.pricing?.company_campaign_price_vat_excl || null,
            company_campaign_price_vat_incl: v.pricing?.company_campaign_price_vat_incl || null,
            campaign_conditions: v.pricing?.campaign_conditions || null,
            campaign_valid_until: v.pricing?.campaign_valid_until || null,
            last_updated: car.last_verified || null
          },
          proposals: car.proposals || [],
          features: car.features_trims || car.features || {},
          pros: car.pros || [],
          cons: car.cons || [],
          technology_advantages: car.technology_advantages || {},
          image_path: car.image_path || "",
          release_year: car.release_year || null,
          official_link: car.official_link || "",
          data_sources: car.data_sources || [],
          powertrain: car.powertrain,
          user_reviews: car.user_reviews || {}
        });
      });
    } else {
      // Single model
      flatCars.push({
        id: `${car.brand}-${car.model}-${car.variant}`.replace(/\s+/g, "-").toLowerCase(),
        brand: car.brand,
        model: car.model,
        variant: car.variant,
        segment: car.segment,
        dimensions: car.dimensions || {},
        specifications: car.specifications || {},
        charging: car.charging || {},
        pricing: car.pricing || {},
        proposals: car.proposals || [],
        features: car.features || {},
        pros: car.pros || [],
        cons: car.cons || [],
        technology_advantages: car.technology_advantages || {},
        image_path: car.image_path || "",
        release_year: car.release_year || null,
        official_link: car.official_link || "",
        data_sources: car.data_sources || [],
        powertrain: car.powertrain,
        user_reviews: car.user_reviews || {}
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

  tabBtns.forEach(btn => {
    const activateTab = () => {
      // Deactivate all
      tabBtns.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
        b.tabIndex = -1;
      });
      tabContents.forEach(c => {
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
      } else if (tabId === "tab-finance") {
        updateFinanceSimulation();
      } else if (tabId === "tab-tco") {
        updateTCO();
      }
    };
    btn.addEventListener("click", activateTab);
    btn.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const buttons = [...tabBtns];
      const current = buttons.indexOf(btn);
      const next = event.key === "Home" ? 0
        : event.key === "End" ? buttons.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next].focus();
      buttons[next].click();
    });
  });
}

/* ==========================================================================
   TAB: Overview Card Rendering
   ========================================================================== */
function renderOverview(filteredList = flatCars) {
  const container = document.getElementById("cars-overview-grid");
  if (!container) return;
  container.innerHTML = "";
  const count = document.getElementById("catalog-count");
  if (count) count.textContent = `${filteredList.length} variantes apresentadas de ${flatCars.length} no catálogo BEV.`;

  if (filteredList.length === 0) {
    container.innerHTML = `
      <div class="glass-panel" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
        <i class="fa-solid fa-car-burst" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 1rem;"></i>
        <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Nenhum carro encontrado</h3>
        <p style="color: var(--text-secondary);">Tenta ajustar os filtros de pesquisa para veres mais opções.</p>
      </div>
    `;
    return;
  }

  filteredList.forEach(car => {
    const card = document.createElement("div");
    card.className = `glass-panel car-card ${car.brand.toLowerCase()}-card`;

    // Formatted prices
    const campaignPrice = car.pricing.particular_campaign_price_vat_incl;
    const listPrice = car.pricing.particular_list_price_vat_incl;
    const displayPrice = campaignPrice || listPrice;

    let priceHTML = "";
    if (displayPrice) {
      priceHTML = `
        <div class="price-main">${formatCurrency(displayPrice)}</div>
        <div class="price-sub">${campaignPrice ? "Campanha c/ IVA" : "PVP c/ IVA"}</div>
      `;
    } else {
      priceHTML = `
        <div class="price-main" style="font-size: 1.1rem; color: var(--text-secondary);">Sob consulta</div>
        <div class="price-sub">Campanha Lançamento</div>
      `;
    }

    // Specs
    const range = car.specifications.wltp_range_combined_km
      ? `${car.specifications.wltp_range_combined_km} km`
      : (car.specifications.wltp_range_urban_km ? `${car.specifications.wltp_range_urban_km} km (Urb)` : "N/A");

    const battery = car.specifications.battery_capacity_kwh
      ? `${car.specifications.battery_capacity_kwh} kWh`
      : "N/A";

    const power = car.specifications.power_hp
      ? `${car.specifications.power_hp} cv`
      : "N/A";

    // Pros & Cons
    const prosHTML = car.pros.map(pro => `<div class="pro-item"><i class="fa-solid fa-check"></i> <span>${pro}</span></div>`).join("");
    const consHTML = car.cons.map(con => `<div class="con-item"><i class="fa-solid fa-xmark"></i> <span>${con}</span></div>`).join("");

    const imagePath = car.image_path || "";
    const imageHTML = imagePath
      ? `<img src="${imagePath}" alt="${car.brand} ${car.model}" class="card-car-image" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
         <div class="card-image-fallback" style="display: none;"><i class="fa-solid fa-car"></i></div>`
      : `<div class="card-image-fallback" style="display: flex;"><i class="fa-solid fa-car"></i></div>`;

    let officialLinkHTML = "";
    if (car.official_link) {
      officialLinkHTML = `
        <a href="${car.official_link}" target="_blank" rel="noopener noreferrer" class="card-official-link" style="display: inline-flex; align-items: center; gap: 0.35rem; color: var(--accent-green); text-decoration: none; font-size: 0.8rem; margin-top: 1rem; font-weight: 600; width: fit-content; transition: color 0.2s;">
          <i class="fa-solid fa-arrow-up-right-from-square"></i> Website Oficial (PT)
        </a>
      `;
    }

    const dealer = typeof DEALER_DATA !== "undefined" ? DEALER_DATA[car.brand] : null;
    const dealerLinkHTML = dealer ? `
      <a href="${dealer.maps_url}" target="_blank" rel="noopener noreferrer" class="card-official-link" style="display: inline-flex; align-items: center; gap: 0.35rem; color: var(--accent-blue); text-decoration: none; font-size: 0.8rem; margin-top: 0.5rem; font-weight: 600; width: fit-content;">
        <i class="fa-solid fa-location-dot"></i> Concessionário mais próximo: ${dealer.name}
      </a>
    ` : "";

    let userReviewHTML = "";
    if (car.user_reviews && car.user_reviews.score) {
      let starsHTML = "";
      const roundedAvg = Math.round(car.user_reviews.score);
      for (let i = 1; i <= 5; i++) {
        if (i <= roundedAvg) {
          starsHTML += "<i class='fa-solid fa-star' style='color: #fbbf24; font-size: 0.8rem; margin-right: 1px;'></i>";
        } else {
          starsHTML += "<i class='fa-regular fa-star' style='color: #d1d5db; font-size: 0.8rem; margin-right: 1px;'></i>";
        }
      }
      userReviewHTML = `
        <div class="card-user-reviews" style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; margin-bottom: 0.75rem;">
          <span style="display: flex;">${starsHTML}</span>
          <span style="font-weight: 700; color: #fbbf24;">${car.user_reviews.score.toFixed(1)}</span>
          <span style="color: var(--text-muted); font-size: 0.75rem;">(${car.user_reviews.total_reviews} avaliações • ${car.user_reviews.source})</span>
        </div>
      `;
    } else {
      userReviewHTML = `
        <div class="card-user-reviews" style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; margin-bottom: 0.75rem;">
          <span style="color: var(--text-muted); font-size: 0.75rem;"><i class="fa-solid fa-star-half-stroke"></i> Sem avaliações de utilizadores</span>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="card-image-wrapper">
        ${imageHTML}
      </div>

      <div class="card-body-content" style="padding: 1.25rem; display: flex; flex-direction: column; flex-grow: 1;">
        <div class="card-header" style="margin-bottom: 1rem;">
          <span class="brand-badge brand-${car.brand.toLowerCase()}">${car.brand}</span>
          <div class="car-price-tag">
            ${priceHTML}
          </div>
        </div>

        <h3 class="car-title">${car.model}</h3>
        <p class="car-segment" style="margin-bottom: 0.5rem;">${car.variant} • ${car.segment || "Segmento"} • 100% elétrico</p>
        ${car.pricing.campaign_conditions ? `<p class="price-conditions">${car.pricing.campaign_conditions}${car.pricing.campaign_valid_until ? ` Válida até ${new Date(`${car.pricing.campaign_valid_until}T00:00:00`).toLocaleDateString("pt-PT")}.` : ""}</p>` : ""}
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

        <div class="pros-cons-section" style="flex-grow: 1;">
          <div>
            <h4>Pontos Fortes</h4>
            <div class="pros-list">${prosHTML || "<p class='no-data-text'>Nenhum adicionado</p>"}</div>
          </div>
          <div style="margin-top: 0.75rem;">
            <h4>Pontos Fracos</h4>
            <div class="cons-list">${consHTML || "<p class='no-data-text'>Nenhum adicionado</p>"}</div>
          </div>
        </div>
        ${officialLinkHTML}
        ${dealerLinkHTML}
      </div>
    `;

    container.appendChild(card);
  });
}

/* ==========================================================================
   TAB: Overview Filters Setup
   ========================================================================== */
function setupFilters() {
  const searchInput = document.getElementById("filter-search");
  const priceSlider = document.getElementById("filter-price");
  const rangeSlider = document.getElementById("filter-range");
  const yearSelect = document.getElementById("filter-year");
  const sortSelect = document.getElementById("filter-sort");
  const btnLilianaRules = document.getElementById("btn-liliana-rules");
  const btnClearFilters = document.getElementById("btn-clear-filters");

  if (searchInput) searchInput.addEventListener("input", () => renderOverview(getFilteredCars()));
  if (priceSlider) priceSlider.addEventListener("input", () => renderOverview(getFilteredCars()));
  if (rangeSlider) rangeSlider.addEventListener("input", () => renderOverview(getFilteredCars()));
  if (yearSelect) yearSelect.addEventListener("change", () => renderOverview(getFilteredCars()));
  if (sortSelect) sortSelect.addEventListener("change", () => renderOverview(getFilteredCars()));

  if (btnLilianaRules) {
    btnLilianaRules.addEventListener("click", () => {
      if (priceSlider) priceSlider.value = "35000";
      if (rangeSlider) rangeSlider.value = "300";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  if (btnClearFilters) {
    btnClearFilters.addEventListener("click", () => {
      if (priceSlider) priceSlider.value = "40000";
      if (rangeSlider) rangeSlider.value = "80";
      if (yearSelect) yearSelect.value = "all";
      if (searchInput) searchInput.value = "";
      renderOverview(getFilteredCars());
    });
  }

  // Run initial calculation to update labels
  getFilteredCars();
}

function getFilteredCars() {
  const searchInput = document.getElementById("filter-search");
  const priceSlider = document.getElementById("filter-price");
  const rangeSlider = document.getElementById("filter-range");
  const yearSelect = document.getElementById("filter-year");
  const sortSelect = document.getElementById("filter-sort");

  const searchVal = searchInput ? searchInput.value : "";
  const maxPriceVal = priceSlider ? parseFloat(priceSlider.value) : 40000;
  const minRangeVal = rangeSlider ? parseFloat(rangeSlider.value) : 80;
  const yearVal = yearSelect ? yearSelect.value : "all";
  const sortVal = sortSelect ? sortSelect.value : "default";

  // Update labels
  const priceDisplay = document.getElementById("filter-price-val");
  const rangeDisplay = document.getElementById("filter-range-val");

  if (priceDisplay) {
    if (maxPriceVal >= 40000) {
      priceDisplay.textContent = "Qualquer";
    } else {
      priceDisplay.textContent = formatCurrency(maxPriceVal);
    }
  }

  if (rangeDisplay) {
    if (minRangeVal <= 80) {
      rangeDisplay.textContent = "Qualquer";
    } else {
      rangeDisplay.textContent = `>= ${minRangeVal} km`;
    }
  }

  const filtered = flatCars.filter(car => {
    // Search filter
    const matchesSearch = VehicleSearch.matchesVehicleSearch(car, searchVal);

    // Price filter (Particular price)
    const price = car.pricing.particular_campaign_price_vat_incl || car.pricing.particular_list_price_vat_incl;
    const matchesPrice = price && price <= maxPriceVal;

    // Autonomy filter
    const range = car.specifications.wltp_range_combined_km || car.specifications.wltp_range_urban_km || 0;
    const matchesRange = minRangeVal <= 80 || (range >= minRangeVal);

    // Release year filter
    let matchesYear = true;
    if (yearVal !== "all") {
      const minYear = parseInt(yearVal);
      matchesYear = car.release_year && (car.release_year >= minYear);
    }

    return matchesSearch && matchesPrice && matchesRange && matchesYear;
  });

  // Apply sorting
  if (sortVal === "price-asc") {
    filtered.sort((a, b) => {
      const pA = a.pricing.particular_campaign_price_vat_incl || a.pricing.particular_list_price_vat_incl || Infinity;
      const pB = b.pricing.particular_campaign_price_vat_incl || b.pricing.particular_list_price_vat_incl || Infinity;
      return pA - pB;
    });
  } else if (sortVal === "price-desc") {
    filtered.sort((a, b) => {
      const pA = a.pricing.particular_campaign_price_vat_incl || a.pricing.particular_list_price_vat_incl || -Infinity;
      const pB = b.pricing.particular_campaign_price_vat_incl || b.pricing.particular_list_price_vat_incl || -Infinity;
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
    filtered.sort((a, b) => VehicleRanking.getPriceRangeScore(b) - VehicleRanking.getPriceRangeScore(a));
  }

  return filtered;
}

/* ==========================================================================
   Dropdowns Population
   ========================================================================== */
function populateDropdowns() {
  const compSelect1 = document.getElementById("comp-select-1");
  const compSelect2 = document.getElementById("comp-select-2");
  const finSelectModel = document.getElementById("fin-select-model");
  const tdSelectModel = document.getElementById("td-select-model");
  const tcoSelectModel = document.getElementById("tco-select-model");

  const selects = [compSelect1, compSelect2, finSelectModel, tdSelectModel, tcoSelectModel];

  selects.forEach(select => {
    if (!select) return;
    select.innerHTML = "";

    flatCars.forEach(car => {
      const option = document.createElement("option");
      option.value = car.id;
      option.textContent = `${car.brand} ${car.model} (${car.variant})`;
      select.appendChild(option);
    });
  });

  // Set defaults
  if (compSelect1 && compSelect2 && flatCars.length >= 2) {
    compSelect1.selectedIndex = 0; // BYD Dolphin Comfort

    // Find Leapmotor B05 Pro as second default for contrast
    const b05Index = flatCars.findIndex(c => c.id.includes("b05-b05-pro"));
    if (b05Index !== -1) {
      compSelect2.selectedIndex = b05Index;
    } else {
      compSelect2.selectedIndex = 1;
    }
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

  const carA = flatCars.find(c => c.id === idA);
  const carB = flatCars.find(c => c.id === idB);

  if (!carA || !carB) return;

  // Update titles
  document.getElementById("th-car-a").textContent = `${carA.brand} ${carA.model} (${carA.variant})`;
  document.getElementById("th-car-b").textContent = `${carB.brand} ${carB.model} (${carB.variant})`;

  // 1. Comparison Bars
  // Max values for scaling
  const maxRange = 500;
  const maxAccel = 13;
  const maxBattery = 80;
  const maxTrunk = 500;

  // Range Combined
  const valRangeA = carA.specifications.wltp_range_combined_km || 0;
  const valRangeB = carB.specifications.wltp_range_combined_km || 0;
  document.getElementById("val-range-a").textContent = valRangeA ? `${valRangeA} km` : "N/A";
  document.getElementById("val-range-b").textContent = valRangeB ? `${valRangeB} km` : "N/A";
  document.getElementById("bar-range-a").style.width = `${Math.min(100, (valRangeA / maxRange) * 100)}%`;
  document.getElementById("bar-range-b").style.width = `${Math.min(100, (valRangeB / maxRange) * 100)}%`;

  // Accel (inverse: lower is better, but bar size represents speed)
  const valAccelA = carA.specifications.acceleration_0_100_s || 0;
  const valAccelB = carB.specifications.acceleration_0_100_s || 0;
  document.getElementById("val-accel-a").textContent = valAccelA ? `${valAccelA}s` : "N/A";
  document.getElementById("val-accel-b").textContent = valAccelB ? `${valAccelB}s` : "N/A";

  // Higher performance (lower 0-100 time) fills more bar
  const pctAccelA = valAccelA ? ((maxAccel - valAccelA) / (maxAccel - 5)) * 100 : 0;
  const pctAccelB = valAccelB ? ((maxAccel - valAccelB) / (maxAccel - 5)) * 100 : 0;
  document.getElementById("bar-accel-a").style.width = `${Math.max(5, Math.min(100, pctAccelA))}%`;
  document.getElementById("bar-accel-b").style.width = `${Math.max(5, Math.min(100, pctAccelB))}%`;

  // Battery
  const valBatteryA = carA.specifications.battery_capacity_kwh || 0;
  const valBatteryB = carB.specifications.battery_capacity_kwh || 0;
  document.getElementById("val-battery-a").textContent = valBatteryA ? `${valBatteryA} kWh` : "N/A";
  document.getElementById("val-battery-b").textContent = valBatteryB ? `${valBatteryB} kWh` : "N/A";
  document.getElementById("bar-battery-a").style.width = `${Math.min(100, (valBatteryA / maxBattery) * 100)}%`;
  document.getElementById("bar-battery-b").style.width = `${Math.min(100, (valBatteryB / maxBattery) * 100)}%`;

  // Trunk
  const valTrunkA = carA.specifications.trunk_capacity_l || 0;
  const valTrunkB = carB.specifications.trunk_capacity_l || 0;
  document.getElementById("val-trunk-a").textContent = valTrunkA ? `${valTrunkA} L` : "N/A";
  document.getElementById("val-trunk-b").textContent = valTrunkB ? `${valTrunkB} L` : "N/A";
  document.getElementById("bar-trunk-a").style.width = `${Math.min(100, (valTrunkA / maxTrunk) * 100)}%`;
  document.getElementById("bar-trunk-b").style.width = `${Math.min(100, (valTrunkB / maxTrunk) * 100)}%`;

  // 2. Comparison Table
  const tbody = document.getElementById("tech-comparison-tbody");
  tbody.innerHTML = "";

  const priceA = carA.pricing.particular_campaign_price_vat_incl || carA.pricing.particular_list_price_vat_incl;
  const priceB = carB.pricing.particular_campaign_price_vat_incl || carB.pricing.particular_list_price_vat_incl;

  const rows = [
    { label: "Marca", valA: carA.brand, valB: carB.brand },
    { label: "Modelo", valA: carA.model, valB: carB.model },
    { label: "Equipamento", valA: carA.variant, valB: carB.variant },
    { label: "Preço Particular c/ IVA", valA: formatCurrency(priceA) || "Sob consulta", valB: formatCurrency(priceB) || "Sob consulta", highlight: true },
    { label: "Avaliação Utilizadores", valA: carA.user_reviews?.score ? `${carA.user_reviews.score.toFixed(1)} / 5 (${carA.user_reviews.total_reviews} avaliações • ${carA.user_reviews.source})` : "N/D", valB: carB.user_reviews?.score ? `${carB.user_reviews.score.toFixed(1)} / 5 (${carB.user_reviews.total_reviews} avaliações • ${carB.user_reviews.source})` : "N/D", highlight: true },
    { label: "Tipo de Bateria", valA: carA.specifications.battery_type, valB: carB.specifications.battery_type },
    { label: "Química da Bateria", valA: carA.technology_advantages?.battery_tech?.chemistry || "N/A", valB: carB.technology_advantages?.battery_tech?.chemistry || "N/A" },
    { label: "Tecnologia Bateria", valA: carA.technology_advantages?.battery_tech?.generation || "N/A", valB: carB.technology_advantages?.battery_tech?.generation || "N/A" },
    { label: "Arquitetura Bateria", valA: carA.technology_advantages?.battery_tech?.architecture || "N/A", valB: carB.technology_advantages?.battery_tech?.architecture || "N/A" },
    { label: "Bomba de Calor Standard", valA: carA.technology_advantages?.battery_tech?.heat_pump_included ? "Sim" : "Não", valB: carB.technology_advantages?.battery_tech?.heat_pump_included ? "Sim" : "Não" },
    { label: "Pré-aquecimento Bateria", valA: carA.technology_advantages?.battery_tech?.battery_preheating ? "Sim" : "Não", valB: carB.technology_advantages?.battery_tech?.battery_preheating ? "Sim" : "Não" },
    { label: "Carregamento Bidirecional V2L", valA: carA.technology_advantages?.bidirectional_charging?.v2l_supported ? `Sim (${carA.technology_advantages.bidirectional_charging.v2l_max_power_kw} kW)` : "Não", valB: carB.technology_advantages?.bidirectional_charging?.v2l_supported ? `Sim (${carB.technology_advantages.bidirectional_charging.v2l_max_power_kw} kW)` : "Não", highlight: true },
    { label: "Capacidade Bateria (kWh)", valA: carA.specifications.battery_capacity_kwh, valB: carB.specifications.battery_capacity_kwh },
    { label: "Autonomia WLTP Mista (km)", valA: carA.specifications.wltp_range_combined_km ? `${carA.specifications.wltp_range_combined_km} km` : "N/A", valB: carB.specifications.wltp_range_combined_km ? `${carB.specifications.wltp_range_combined_km} km` : "N/A", highlight: true },
    { label: "Autonomia WLTP Urbana (km)", valA: carA.specifications.wltp_range_urban_km ? `${carA.specifications.wltp_range_urban_km} km` : "N/A", valB: carB.specifications.wltp_range_urban_km ? `${carB.specifications.wltp_range_urban_km} km` : "N/A" },
    { label: "Consumo Misto (kWh/100km)", valA: carA.specifications.wltp_consumption_combined_kwh_100km ? `${carA.specifications.wltp_consumption_combined_kwh_100km} kWh` : "N/A", valB: carB.specifications.wltp_consumption_combined_kwh_100km ? `${carB.specifications.wltp_consumption_combined_kwh_100km} kWh` : "N/A" },
    { label: "Potência Máxima", valA: carA.specifications.power_hp ? `${carA.specifications.power_hp} cv (${carA.specifications.power_kw} kW)` : "N/A", valB: carB.specifications.power_hp ? `${carB.specifications.power_hp} cv (${carB.specifications.power_kw} kW)` : "N/A" },
    { label: "Binário Motor", valA: carA.specifications.torque_nm ? `${carA.specifications.torque_nm} Nm` : "N/A", valB: carB.specifications.torque_nm ? `${carB.specifications.torque_nm} Nm` : "N/A" },
    { label: "Aceleração 0-100 km/h", valA: carA.specifications.acceleration_0_100_s ? `${carA.specifications.acceleration_0_100_s} seg` : "N/A", valB: carB.specifications.acceleration_0_100_s ? `${carB.specifications.acceleration_0_100_s} seg` : "N/A", highlight: true },
    { label: "Tração", valA: carA.brand === "Leapmotor" || carA.brand === "Volvo" || carA.brand === "MG" ? "Traseira (RWD)" : "Dianteira (FWD)", valB: carB.brand === "Leapmotor" || carB.brand === "Volvo" || carB.brand === "MG" ? "Traseira (RWD)" : "Dianteira (FWD)" },
    { label: "Suspensão Traseira", valA: carA.specifications.suspension_rear || "N/A", valB: carB.specifications.suspension_rear || "N/A" },
    { label: "Capacidade Bagageira", valA: carA.specifications.trunk_capacity_l ? `${carA.specifications.trunk_capacity_l} L` : "N/A", valB: carB.specifications.trunk_capacity_l ? `${carB.specifications.trunk_capacity_l} L` : "N/A" },
    { label: "Comprimento Exterior", valA: carA.dimensions.length_mm ? `${carA.dimensions.length_mm / 1000} m` : "N/A", valB: carB.dimensions.length_mm ? `${carB.dimensions.length_mm / 1000} m` : "N/A" },
    { label: "Largura Exterior", valA: carA.dimensions.width_mm ? `${carA.dimensions.width_mm / 1000} m` : "N/A", valB: carB.dimensions.width_mm ? `${carB.dimensions.width_mm / 1000} m` : "N/A" },
    { label: "Altura Exterior", valA: carA.dimensions.height_mm ? `${carA.dimensions.height_mm / 1000} m` : "N/A", valB: carB.dimensions.height_mm ? `${carB.dimensions.height_mm / 1000} m` : "N/A" },
    { label: "Distância entre Eixos", valA: carA.dimensions.wheelbase_mm ? `${carA.dimensions.wheelbase_mm} mm` : "N/A", valB: carB.dimensions.wheelbase_mm ? `${carB.dimensions.wheelbase_mm} mm` : "N/A" },
    { label: "Raio de Viragem", valA: carA.dimensions.turning_radius_m ? `${carA.dimensions.turning_radius_m} m` : "N/A", valB: carB.dimensions.turning_radius_m ? `${carB.dimensions.turning_radius_m} m` : "N/A" },
    { label: "Potência Máxima DC", valA: carA.charging.dc_max_kw ? `${carA.charging.dc_max_kw} kW` : "N/A", valB: carB.charging.dc_max_kw ? `${carB.charging.dc_max_kw} kW` : "N/A" },
    { label: "Carregamento DC 30-80%", valA: carA.charging.dc_charge_time_30_80_min ? `${carA.charging.dc_charge_time_30_80_min} min` : "N/A", valB: carB.charging.dc_charge_time_30_80_min ? `${carB.charging.dc_charge_time_30_80_min} min` : "N/A", highlight: true },
    { label: "Processador Infotainment", valA: carA.technology_advantages?.infotainment_tech?.processor || "N/A", valB: carB.technology_advantages?.infotainment_tech?.processor || "N/A" },
    { label: "Google Built-in", valA: carA.technology_advantages?.infotainment_tech?.google_built_in ? "Sim" : "Não", valB: carB.technology_advantages?.infotainment_tech?.google_built_in ? "Sim" : "Não" },
    { label: "Atualizações OTA", valA: carA.technology_advantages?.infotainment_tech?.ota_updates ? "Sim" : "Não", valB: carB.technology_advantages?.infotainment_tech?.ota_updates ? "Sim" : "Não" }
  ];

  rows.forEach(r => {
    const tr = document.createElement("tr");

    const tdLabel = document.createElement("td");
    tdLabel.className = "cat-label";
    tdLabel.textContent = r.label;
    tr.appendChild(tdLabel);

    const tdValA = document.createElement("td");
    tdValA.className = r.highlight ? "val-highlight accent-color" : "";
    tdValA.textContent = r.valA !== null ? r.valA : "N/A";
    tr.appendChild(tdValA);

    const tdValB = document.createElement("td");
    tdValB.className = r.highlight ? "val-highlight" : "";
    tdValB.style.color = r.highlight ? "var(--accent-purple)" : "";
    tdValB.textContent = r.valB !== null ? r.valB : "N/A";
    tr.appendChild(tdValB);

    tbody.appendChild(tr);
  });
}

/* ==========================================================================
   TAB: Credit Simulator Logic
   ========================================================================== */
function setupFinanceSimulator() {
  const finSelectModel = document.getElementById("fin-select-model");
  const finInputPrice = document.getElementById("fin-input-price");
  const finRangeDownpayment = document.getElementById("fin-range-downpayment");
  const finRangeTerm = document.getElementById("fin-range-term");
  const finRangeRate = document.getElementById("fin-range-rate");
  const finInputFees = document.getElementById("fin-input-fees");

  if (!finSelectModel) return;

  // Set initial input price when selecting a model
  finSelectModel.addEventListener("change", () => {
    const selectedCar = flatCars.find(c => c.id === finSelectModel.value);
    if (selectedCar) {
      const price = selectedCar.pricing.particular_campaign_price_vat_incl || selectedCar.pricing.particular_list_price_vat_incl;
      finInputPrice.value = price ? Math.round(price) : "";
      finInputPrice.placeholder = price ? "" : "Introduza um PVP confirmado";

      // Update fees base estimate
      // BYD Dolphin simulation had contract fee 750 + ISUC stamp duty
      if (selectedCar.brand === "BYD") {
        finInputFees.value = selectedCar.id.includes("surf") ? 1038 : 1182; // roughly matches real proposal fees (Despesas + ISUC)
      } else {
        finInputFees.value = 1100;
      }

      updateFinanceSimulation();
    }
  });

  // Trigger update on any input change
  const inputs = [finInputPrice, finRangeDownpayment, finRangeTerm, finRangeRate, finInputFees];
  inputs.forEach(input => {
    input.addEventListener("input", updateFinanceSimulation);
  });

  // Initialize
  finSelectModel.dispatchEvent(new Event("change"));
}

function updateFinanceSimulation() {
  const finSelectModel = document.getElementById("fin-select-model");
  const priceInput = document.getElementById("fin-input-price");
  const hasPrice = priceInput.value.trim() !== "" && Number.isFinite(Number(priceInput.value));
  const price = hasPrice ? Math.max(0, parseFloat(priceInput.value)) : 0;
  let downpayment = parseFloat(document.getElementById("fin-range-downpayment").value) || 0;
  const term = parseInt(document.getElementById("fin-range-term").value) || 12;
  const rateTAN = parseFloat(document.getElementById("fin-range-rate").value) || 0;
  const fees = parseFloat(document.getElementById("fin-input-fees").value) || 0;

  // Update label values
  document.getElementById("fin-downpayment-val").textContent = formatCurrency(downpayment);
  document.getElementById("fin-term-val").textContent = `${term} meses`;
  document.getElementById("fin-rate-val").textContent = `${rateTAN.toFixed(2).replace(".", ",")} %`;

  // Restrict downpayment logic (cannot exceed price)
  const maxDown = Math.min(price, 25000);
  const downpaymentInput = document.getElementById("fin-range-downpayment");
  downpaymentInput.max = maxDown;
  if (downpayment > maxDown) {
    downpayment = maxDown;
    downpaymentInput.value = maxDown;
    document.getElementById("fin-downpayment-val").textContent = formatCurrency(downpayment);
  }

  const selectedCar = flatCars.find(c => c.id === finSelectModel.value);
  document.getElementById("fin-result-badge").textContent = selectedCar
    ? `${selectedCar.brand} ${selectedCar.model} (${selectedCar.variant})`
    : "Simulação";

  // Calculation formulas
  // Amount to finance = Price - Downpayment + Financed Fees
  const financedAmount = Math.max(0, price - downpayment);
  const totalFinancedWithFees = financedAmount + fees;

  let monthlyPayment = 0;
  if (totalFinancedWithFees > 0) {
    if (rateTAN > 0) {
      const monthlyRate = (rateTAN / 100) / 12;
      monthlyPayment = (totalFinancedWithFees * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -term));
    } else {
      monthlyPayment = totalFinancedWithFees / term;
    }
  }

  // Total of installments (MTIC)
  const mtic = monthlyPayment * term;
  const grandTotalCost = mtic + downpayment;

  // Render results
  document.getElementById("fin-result-monthly").textContent = hasPrice ? formatCurrency(monthlyPayment) : "—";
  document.getElementById("fin-breakdown-pvp").textContent = hasPrice ? formatCurrency(price) : "—";
  document.getElementById("fin-breakdown-downpayment").textContent = formatCurrency(downpayment);
  document.getElementById("fin-breakdown-financed").textContent = hasPrice ? formatCurrency(financedAmount) : "—";
  document.getElementById("fin-breakdown-fees").textContent = formatCurrency(fees);
  document.getElementById("fin-breakdown-mtic").textContent = hasPrice ? formatCurrency(mtic) : "—";
  document.getElementById("fin-breakdown-total-cost").textContent = hasPrice ? formatCurrency(grandTotalCost) : "—";

  // Render comparison with REAL proposals
  const comparisonBox = document.getElementById("fin-proposal-comparison-content");
  if (!selectedCar || selectedCar.proposals.length === 0) {
    comparisonBox.innerHTML = "<p class='no-data-text'>Sem propostas bancárias reais para este modelo na base de dados.</p>";
  } else {
    // There is a proposal
    const prop = selectedCar.proposals[0];
    const realFin = prop.financing;

    // Check if simulation parameters match the proposal's original parameters
    const matchesOriginal = Math.abs(downpayment - realFin.downpayment_eur) < 5
      && term === realFin.term_months
      && Math.abs(rateTAN - realFin.nominal_rate_pct) < 0.1;

    let matchHTML = "";
    if (matchesOriginal) {
      const diff = monthlyPayment - realFin.monthly_payment_eur;
      const diffText = diff > 0
        ? `+${diff.toFixed(2)} €/mês`
        : `${diff.toFixed(2)} €/mês`;

      matchHTML = `
        <span class="comp-diff-label" style="color: ${diff > 1 ? 'var(--accent-red)' : 'var(--accent-green)'}">
          Diferença para Proposta: ${diffText} (taxas adicionais bancárias)
        </span>
      `;
    } else {
      matchHTML = `<span class="comp-diff-label" style="color: var(--text-secondary)">Parâmetros customizados (proposta original simulada com ${formatCurrency(realFin.downpayment_eur)} de entrada, ${realFin.term_months}m e TAN ${realFin.nominal_rate_pct}%)</span>`;
    }

    comparisonBox.innerHTML = `
      <div class="comp-detail-row">
        <span>Concessionário / Proposta:</span>
        <span>${prop.dealer} (${prop.proposal_number})</span>
      </div>
      <div class="comp-detail-row">
        <span>Prestação Real na Proposta:</span>
        <span class="accent-color">${formatCurrency(realFin.monthly_payment_eur)}</span>
      </div>
      <div class="comp-detail-row">
        <span>Impostos & Taxas Reais (financiadas):</span>
        <span>${formatCurrency(realFin.contract_fee_eur + realFin.isuc_eur)}</span>
      </div>
      <div class="comp-detail-row">
        <span>Total Pago Real (Entrada + MTIC):</span>
        <span>${formatCurrency(realFin.total_cost_eur)}</span>
      </div>
      ${matchHTML}
    `;
  }
}

/* ==========================================================================
   TAB: TCO Savings
   ========================================================================== */
function setupTCOSavings() {
  const kmInput = document.getElementById("tco-range-km");
  const elecInput = document.getElementById("tco-range-elec-price");
  const fuelInput = document.getElementById("tco-range-fuel-price");
  const refConsInput = document.getElementById("tco-ref-consumption");
  const modelInput = document.getElementById("tco-select-model");

  const inputs = [kmInput, elecInput, fuelInput, refConsInput, modelInput];
  inputs.forEach(input => {
    if (input) input.addEventListener("input", updateTCO);
  });
}

function updateTCO() {
  const annualKm = parseFloat(document.getElementById("tco-range-km").value) || 0;
  const elecPrice = parseFloat(document.getElementById("tco-range-elec-price").value) || 0.22;
  const fuelPrice = parseFloat(document.getElementById("tco-range-fuel-price").value) || 1.78;
  const refConsumption = parseFloat(document.getElementById("tco-ref-consumption").value) || 6.5;

  document.getElementById("tco-km-val").textContent = `${formatNumber(annualKm)} km`;
  document.getElementById("tco-elec-val").textContent = `${elecPrice.toFixed(2).replace(".", ",")} €`;
  document.getElementById("tco-fuel-val").textContent = `${fuelPrice.toFixed(2).replace(".", ",")} €`;

  // Calculate gas reference cost
  const gasAnnualCost = (annualKm / 100) * refConsumption * fuelPrice;

  // Generate comparison items
  const chartContainer = document.getElementById("tco-chart-container");
  chartContainer.innerHTML = "";

  // Add Gasolina Bar
  renderTCOBar(chartContainer, "Carro Gasolina Equivalente", gasAnnualCost, "gasolina", 1.0);

  const selectedId = document.getElementById("tco-select-model")?.value;
  const car = flatCars.find(item => item.id === selectedId) || flatCars[0];
  const cons = car?.specifications.wltp_consumption_combined_kwh_100km;
  const annualElecCost = cons ? (annualKm / 100) * cons * elecPrice : 0;
  const ratio = gasAnnualCost ? annualElecCost / gasAnnualCost : 0;
  if (car && cons) renderTCOBar(chartContainer, `${car.brand} ${car.model} (${car.variant})`, annualElecCost, "eletrico", ratio);
  const maxSavings = Math.max(0, gasAnnualCost - annualElecCost);

  // Update savings summary card
  document.getElementById("tco-savings-title").textContent = `Poupança Estimada: ${formatCurrency(maxSavings)} / ano`;
  document.getElementById("tco-savings-text").textContent = `A carregar em casa a eletricidade, poupa até ${formatCurrency(maxSavings / 12)} por mês comparando com um carro a gasolina (${refConsumption}L/100km).`;
}

function renderTCOBar(container, label, cost, type, ratio) {
  const row = document.createElement("div");
  row.className = "tco-bar-row";

  const widthPct = Math.max(15, Math.min(100, ratio * 100));

  row.innerHTML = `
    <div class="tco-bar-lbl">
      <span>${label}</span>
      <span>${formatCurrency(cost)} / ano</span>
    </div>
    <div class="tco-bar-bg">
      <div class="tco-bar-fill ${type}" style="width: ${widthPct}%">
        ${formatCurrency(cost)}
      </div>
    </div>
  `;

  container.appendChild(row);
}

/* ==========================================================================
   TAB: Test Drives Scoring & Persistency
   ========================================================================== */
function setupTestDriveScores() {
  const starsContainer = document.querySelectorAll(".stars-rating");
  starsContainer.forEach(container => {
    const category = container.getAttribute("data-category");
    const stars = container.querySelectorAll(".star-btn");

    stars.forEach(star => {
      // Hover highlight
      star.addEventListener("mouseenter", () => {
        const val = parseInt(star.getAttribute("data-value"));
        highlightStars(container, val);
      });

      star.addEventListener("mouseleave", () => {
        const currentRating = parseInt(container.getAttribute("data-rating") || "0");
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
  document.getElementById("btn-save-testdrive").addEventListener("click", saveReview);
}

function highlightStars(container, rating) {
  const stars = container.querySelectorAll(".star-btn");
  stars.forEach(star => {
    const val = parseInt(star.getAttribute("data-value"));
    const icon = star.querySelector("i");
    icon.className = val <= rating ? "fa-star fa-solid" : "fa-star fa-regular";
    star.setAttribute("aria-pressed", val <= rating ? "true" : "false");
  });
}

function saveReview() {
  const carId = document.getElementById("td-select-model").value;
  const car = flatCars.find(c => c.id === carId);
  const notes = document.getElementById("td-input-notes").value.trim();

  if (!car) return;

  // Collect scores
  const scores = {};
  const categories = ["comfort", "space", "tech", "design", "value"];
  let totalScore = 0;

  categories.forEach(cat => {
    const container = document.querySelector(`.stars-rating[data-category="${cat}"]`);
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
    notes: notes
  };

  // Add to reviews list
  testDriveReviews = testDriveReviews.filter(r => r.carId !== carId); // override previous review for this car
  testDriveReviews.unshift(newReview);

  // Save to LocalStorage
  localStorage.setItem("carro_liliana_reviews", JSON.stringify(testDriveReviews));

  // Reset form
  document.getElementById("td-input-notes").value = "";
  const starsContainers = document.querySelectorAll(".stars-rating");
  starsContainers.forEach(container => {
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
      testDriveReviews = Array.isArray(parsed) ? parsed.filter(isValidReview) : [];
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
    listContainer.innerHTML = "<p class='no-data-text'>Sem avaliações registadas para já.</p>";
    return;
  }

  listContainer.innerHTML = "";
  testDriveReviews.forEach(review => {
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
      icon.className = i <= roundedAvg ? "fa-solid fa-star" : "fa-regular fa-star";
      icon.setAttribute("aria-hidden", "true");
      stars.appendChild(icon);
    }
    stars.appendChild(document.createTextNode(` (${review.average.toFixed(1)})`));
    header.append(title, stars);
    const date = document.createElement("small");
    date.textContent = `Avaliado a ${review.date}`;
    const notes = document.createElement("div");
    notes.className = "review-card-notes";
    notes.textContent = review.notes || "Sem notas de texto, apenas pontuações.";
    const details = document.createElement("div");
    details.className = "review-score-details";
    details.textContent = `Conforto: ${review.scores.comfort}/5 · Espaço: ${review.scores.space}/5 · Tecnologia: ${review.scores.tech}/5 · Design: ${review.scores.design}/5 · Relação preço: ${review.scores.value}/5`;
    card.append(header, date, notes, details);
    listContainer.appendChild(card);
  });
}

function isValidReview(review) {
  if (!review || typeof review !== "object" || typeof review.carName !== "string" ||
      typeof review.notes !== "string" || !Number.isFinite(review.average) ||
      !review.scores || typeof review.scores !== "object") return false;
  return ["comfort", "space", "tech", "design", "value"].every(key =>
    Number.isInteger(review.scores[key]) && review.scores[key] >= 0 && review.scores[key] <= 5
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
    maximumFractionDigits: 2
  }).format(val);
}

function formatNumber(val) {
  if (val === null || val === undefined) return "";
  return new Intl.NumberFormat("pt-PT").format(val);
}

// Safer parse
function jsonParse(str) {
  try {
    return JSON.parse(str);
  } catch (e) {
    return null;
  }
}

function renderStands() {
  const container = document.getElementById("dynamic-stands-list");
  if (!container) return;
  container.innerHTML = "";

  // Get list of unique brands present in our flatCars array
  const activeBrands = [...new Set(flatCars.map(car => car.brand))];

  activeBrands.forEach(brand => {
    const dealer = typeof DEALER_DATA !== "undefined" ? DEALER_DATA[brand] : null;
    if (!dealer) return;

    const standItem = document.createElement("div");
    standItem.className = "stand-item";

    standItem.innerHTML = `
      <div class="stand-badge brand-${brand.toLowerCase()}">${brand}</div>
      <div class="stand-details">
        <h4>${dealer.name}</h4>
        <p><i class="fa-solid fa-map-location-dot"></i> ${dealer.address}, ${dealer.postal_code} ${dealer.locality}</p>
        ${dealer.email ? `<p><i class="fa-solid fa-envelope"></i> <a href="mailto:${dealer.email}" style="color: var(--text-secondary); text-decoration: none;">${dealer.email}</a></p>` : ""}
        <p><i class="fa-solid fa-phone"></i> <a href="tel:${dealer.phone.replace(/\s+/g, "")}" style="color: var(--text-secondary); text-decoration: none;">${dealer.phone}</a></p>
        <p><i class="fa-solid fa-route"></i> <a href="${dealer.maps_url}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-blue);">Como chegar</a> · <a href="${dealer.official_url}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-green);">Página oficial</a></p>
      </div>
    `;
    container.appendChild(standItem);
  });
}
