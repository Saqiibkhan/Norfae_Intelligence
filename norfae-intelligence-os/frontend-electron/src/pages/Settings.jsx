import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../services/api";

export default function Settings() {
  // ===================================
  // SHOPIFY
  // ===================================

  const [shopifyStoreUrl, setShopifyStoreUrl] = useState("");

  const [shopifyAccessToken, setShopifyAccessToken] = useState("");

  // ===================================
  // META ADS
  // ===================================

  const [metaAccountId, setMetaAccountId] = useState("");

  const [metaAccessToken, setMetaAccessToken] = useState("");

  // ===================================
  // DELIVERY SETTINGS
  // ===================================

  const [gstPercentage, setGstPercentage] = useState(16);

  const [fuelSurcharge, setFuelSurcharge] = useState(30);

  const [codPercentage, setCodPercentage] = useState(4);

  const [packagingCost, setPackagingCost] = useState(50);

  const [warehouseCity, setWarehouseCity] = useState("Lahore");

  const [warehouseProvince, setWarehouseProvince] = useState("Punjab");

  // ===================================
  // SAME CITY
  // ===================================

  const [sameCityHalfKg, setSameCityHalfKg] = useState(100);

  const [sameCityOneKg, setSameCityOneKg] = useState(140);

  const [sameCityAdditional, setSameCityAdditional] = useState(40);

  // ===================================
  // SAME PROVINCE
  // ===================================

  const [sameProvinceHalfKg, setSameProvinceHalfKg] = useState(120);

  const [sameProvinceOneKg, setSameProvinceOneKg] = useState(160);

  const [sameProvinceAdditional, setSameProvinceAdditional] = useState(50);

  // ===================================
  // OTHER PROVINCE
  // ===================================

  const [otherProvinceHalfKg, setOtherProvinceHalfKg] = useState(140);

  const [otherProvinceOneKg, setOtherProvinceOneKg] = useState(190);

  const [otherProvinceAdditional, setOtherProvinceAdditional] = useState(60);

  const [loading, setLoading] = useState(false);

  const [saving, setSaving] = useState(false);

  // ===================================
  // FETCH SETTINGS
  // ===================================

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await api.get("/settings/");

      const settings = response.data;

      // ===================================
      // SHOPIFY
      // ===================================

      setShopifyStoreUrl(settings.shopify_store_url || "");

      setShopifyAccessToken(settings.shopify_access_token || "");

      // ===================================
      // META ADS
      // ===================================

      setMetaAccountId(settings.meta_account_id || "");

      setMetaAccessToken(settings.meta_access_token || "");

      // ===================================
      // DELIVERY
      // ===================================

      setGstPercentage(settings.gst_percentage || 0);

      setFuelSurcharge(settings.fuel_surcharge_percentage || 0);

      setCodPercentage(settings.income_tax_percentage || 0);

      setPackagingCost(settings.packaging_cost || 0);

      setWarehouseCity(settings.warehouse_city || "");

      setWarehouseProvince(settings.warehouse_province || "");

      // ===================================
      // SAME CITY
      // ===================================

      setSameCityHalfKg(settings.same_city_half_kg || 0);

      setSameCityOneKg(settings.same_city_one_kg || 0);

      setSameCityAdditional(settings.same_city_additional_half_kg || 0);

      // ===================================
      // SAME PROVINCE
      // ===================================

      setSameProvinceHalfKg(settings.same_province_half_kg || 0);

      setSameProvinceOneKg(settings.same_province_one_kg || 0);

      setSameProvinceAdditional(settings.same_province_additional_half_kg || 0);

      // ===================================
      // OTHER PROVINCE
      // ===================================

      setOtherProvinceHalfKg(settings.other_province_half_kg || 0);

      setOtherProvinceOneKg(settings.other_province_one_kg || 0);

      setOtherProvinceAdditional(
        settings.other_province_additional_half_kg || 0,
      );
    } catch (error) {
      console.log(error);
      toast.error("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadSettings = async () => {
      await fetchSettings();
    };

    loadSettings();
  }, []);

  // ===================================
  // SAVE SETTINGS
  // ===================================

  const saveSettings = async () => {
    try {
      setSaving(true);
      await api.post(
        "/settings/",

        {
          // ===================================
          // SHOPIFY
          // ===================================

          shopify_store_url: shopifyStoreUrl,

          shopify_access_token: shopifyAccessToken,

          // ===================================
          // META ADS
          // ===================================

          meta_account_id: metaAccountId,

          meta_access_token: metaAccessToken,

          // ===================================
          // TAXES
          // ===================================

          gst_percentage: Number(gstPercentage),

          fuel_surcharge_percentage: Number(fuelSurcharge),

          income_tax_percentage: Number(codPercentage),

          // ===================================
          // OPERATIONS
          // ===================================

          packaging_cost: Number(packagingCost),

          warehouse_city: warehouseCity,

          warehouse_province: warehouseProvince,

          // ===================================
          // SAME CITY
          // ===================================

          same_city_half_kg: Number(sameCityHalfKg),

          same_city_one_kg: Number(sameCityOneKg),

          same_city_additional_half_kg: Number(sameCityAdditional),

          // ===================================
          // SAME PROVINCE
          // ===================================

          same_province_half_kg: Number(sameProvinceHalfKg),

          same_province_one_kg: Number(sameProvinceOneKg),

          same_province_additional_half_kg: Number(sameProvinceAdditional),

          // ===================================
          // OTHER PROVINCE
          // ===================================

          other_province_half_kg: Number(otherProvinceHalfKg),

          other_province_one_kg: Number(otherProvinceOneKg),

          other_province_additional_half_kg: Number(otherProvinceAdditional),
        },
      );

      toast.success("Settings saved successfully");
    } catch (error) {
      console.log(error);

      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  // ===================================
  // UI HELPERS
  // ===================================

  const inputStyle = `
    w-full
    h-[56px]
    px-5
    rounded-2xl
    bg-[#0F172A]
    border
    border-slate-800
    text-white
    outline-none
    transition-all
    focus:border-cyan-400/40
    focus:bg-[#111827]
  `;

  const cardStyle = `
    bg-gradient-to-br
    from-[#081028]
    to-[#050B1A]
    border
    border-cyan-500/10
    rounded-[32px]
    p-8
  `;

  if (loading) {
    return <div className="p-10 text-white text-lg">Loading Settings...</div>;
  }

  return (
    <div className="min-h-screen bg-[#020817] text-white p-8">
      {/* =================================== */}
      {/* HEADER */}
      {/* =================================== */}

      <div className="mb-10">
        <div
          className="
            inline-flex
            items-center
            px-5
            py-2
            rounded-full
            border
            border-cyan-400/20
            bg-cyan-400/10
            text-cyan-300
            text-sm
            font-bold
            mb-5
          "
        >
          SYSTEM CONFIGURATION
        </div>

        <h1
          className="
            text-5xl
            font-black
            tracking-tight
            mb-3
          "
        >
          Settings
        </h1>

        <p
          className="
            text-slate-400
            text-xl
          "
        >
          Configure integrations, delivery intelligence and operational systems
        </p>
      </div>

      {/* =================================== */}
      {/* TOP GRID */}
      {/* =================================== */}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* SHOPIFY */}

        <div className={cardStyle}>
          <h2 className="text-4xl font-black mb-8">Shopify</h2>

          <div className="space-y-6">
            <div>
              <p className="mb-3 text-slate-400 text-sm font-semibold uppercase">
                Store URL
              </p>

              <input
                type="text"
                value={shopifyStoreUrl}
                onChange={(e) => setShopifyStoreUrl(e.target.value)}
                className={inputStyle}
              />
            </div>

            <div>
              <p className="mb-3 text-slate-400 text-sm font-semibold uppercase">
                Access Token
              </p>

              <input
                type="text"
                value={shopifyAccessToken}
                onChange={(e) => setShopifyAccessToken(e.target.value)}
                className={inputStyle}
              />
            </div>

            <button
              onClick={saveSettings}
              disabled={saving}
              className="
                w-full
                h-[58px]
                rounded-2xl
                bg-gradient-to-r
                from-cyan-500
                to-blue-600
                font-bold
                text-lg
                hover:scale-[1.01]
                transition-all
              "
            >
              {saving ? "Saving..." : "Save Shopify Settings"}
            </button>
          </div>
        </div>

        {/* META ADS */}

        <div className={cardStyle}>
          <h2 className="text-4xl font-black mb-8">Meta Ads</h2>

          <div className="space-y-6">
            <div>
              <p className="mb-3 text-slate-400 text-sm font-semibold uppercase">
                Ad Account ID
              </p>

              <input
                type="text"
                value={metaAccountId}
                onChange={(e) => setMetaAccountId(e.target.value)}
                className={inputStyle}
              />
            </div>

            <div>
              <p className="mb-3 text-slate-400 text-sm font-semibold uppercase">
                Access Token
              </p>

              <input
                type="text"
                value={metaAccessToken}
                onChange={(e) => setMetaAccessToken(e.target.value)}
                className={inputStyle}
              />
            </div>

            <button
              onClick={saveSettings}
              disabled={saving}
              className="
                w-full
                h-[58px]
                rounded-2xl
                bg-gradient-to-r
                from-cyan-500
                to-blue-600
                font-bold
                text-lg
                hover:scale-[1.01]
                transition-all
              "
            >
              {saving ? "Saving..." : "Save Meta Settings"}
            </button>
          </div>
        </div>
      </div>

      {/* ===================================
          DELIVERY INTELLIGENCE
      =================================== */}

      <div className={`${cardStyle} mt-8`}>
        <h2 className="text-5xl font-black mb-3">Delivery Intelligence</h2>

        <p className="text-slate-400 text-lg mb-10">
          Configure courier rates, taxes and operational logistics
        </p>

        {/* ===================================
            BUSINESS SETTINGS
        =================================== */}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {[
            {
              label: "GST Percentage",
              value: gstPercentage,
              setter: setGstPercentage,
            },
            {
              label: "Fuel Surcharge Percentage",
              value: fuelSurcharge,
              setter: setFuelSurcharge,
            },
            {
              label: "COD Tax Percentage",
              value: codPercentage,
              setter: setCodPercentage,
            },
            {
              label: "Packaging Cost",
              value: packagingCost,
              setter: setPackagingCost,
            },
            {
              label: "Warehouse City",
              value: warehouseCity,
              setter: setWarehouseCity,
              type: "text",
            },
            {
              label: "Warehouse Province",
              value: warehouseProvince,
              setter: setWarehouseProvince,
              type: "text",
            },
          ].map((field) => (
            <div key={field.label}>
              <p className="mb-3 text-slate-400 text-sm font-semibold uppercase">
                {field.label}
              </p>

              <input
                type={field.type || "number"}
                value={field.value}
                onChange={(e) => field.setter(e.target.value)}
                className={inputStyle}
              />
            </div>
          ))}
        </div>

        {/* ===================================
            RATE CARDS
        =================================== */}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mt-12">
          {[
            {
              title: "Same City Rates",
              values: [
                {
                  label: "Up To 0.5 KG",
                  value: sameCityHalfKg,
                  setter: setSameCityHalfKg,
                },
                {
                  label: "Up To 1 KG",
                  value: sameCityOneKg,
                  setter: setSameCityOneKg,
                },
                {
                  label: "Additional 0.5 KG",
                  value: sameCityAdditional,
                  setter: setSameCityAdditional,
                },
              ],
            },

            {
              title: "Same Province Rates",
              values: [
                {
                  label: "Up To 0.5 KG",
                  value: sameProvinceHalfKg,
                  setter: setSameProvinceHalfKg,
                },
                {
                  label: "Up To 1 KG",
                  value: sameProvinceOneKg,
                  setter: setSameProvinceOneKg,
                },
                {
                  label: "Additional 0.5 KG",
                  value: sameProvinceAdditional,
                  setter: setSameProvinceAdditional,
                },
              ],
            },

            {
              title: "Other Province Rates",
              values: [
                {
                  label: "Up To 0.5 KG",
                  value: otherProvinceHalfKg,
                  setter: setOtherProvinceHalfKg,
                },
                {
                  label: "Up To 1 KG",
                  value: otherProvinceOneKg,
                  setter: setOtherProvinceOneKg,
                },
                {
                  label: "Additional 0.5 KG",
                  value: otherProvinceAdditional,
                  setter: setOtherProvinceAdditional,
                },
              ],
            },
          ].map((section) => (
            <div
              key={section.title}
              className="
                bg-[#0B1220]
                border
                border-slate-800
                rounded-3xl
                p-6
              "
            >
              <h3 className="text-2xl font-black mb-6">{section.title}</h3>

              <div className="space-y-5">
                {section.values.map((item) => (
                  <div key={item.label}>
                    <p className="mb-2 text-slate-400 text-sm font-semibold">
                      {item.label}
                    </p>

                    <input
                      type="number"
                      value={item.value}
                      onChange={(e) => item.setter(e.target.value)}
                      className={inputStyle}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* ===================================
            SAVE BUTTON
        =================================== */}

        <div className="mt-12 flex justify-end">
          <button
            onClick={saveSettings}
            disabled={saving}
            className="
              px-10
              h-[60px]
              rounded-2xl
              bg-gradient-to-r
              from-cyan-500
              to-blue-600
              text-lg
              font-black
              hover:scale-[1.02]
              transition-all
            "
          >
            {saving ? "Saving..." : "Save Delivery Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
