import { useEffect, useState } from "react";

import DatePicker from "react-datepicker";

import "react-datepicker/dist/react-datepicker.css";

import { getPakistanDate } from "../utils/pakistanDate";

import { getAllTimeRange } from "../utils/dateFilters";

import {
  fetchMetaOverview,
  fetchCampaigns,
  fetchAdsets,
  fetchAds,
} from "../lib/metaAdsApi";

import { toast } from "sonner";

const getPakistanYesterday = () => {
  const date = new Date();

  date.setDate(date.getDate() - 1);

  return date.toLocaleDateString("en-CA", {
    timeZone: "Asia/Karachi",
  });
};

function MetaAds() {
  const [overview, setOverview] = useState(null);

  const [campaigns, setCampaigns] = useState([]);

  const [adsets, setAdsets] = useState([]);

  const [ads, setAds] = useState([]);

  const [selectedCampaign, setSelectedCampaign] = useState(null);

  const [selectedAdset, setSelectedAdset] = useState(null);

  const [loading, setLoading] = useState(true);

  const [selectedFilter, setSelectedFilter] = useState("today");

  const [customStartDate, setCustomStartDate] = useState(null);

  const [customEndDate, setCustomEndDate] = useState(null);

  const [appliedStartDate, setAppliedStartDate] = useState(null);

  const [appliedEndDate, setAppliedEndDate] = useState(null);

  const loadMetaData = async (startDate, endDate) => {
    console.log("META DATE RANGE");
    console.log("startDate:", startDate);
    console.log("endDate:", endDate);

    try {
      setLoading(true);

      const [overviewData, campaignsData, adsetsData, adsData] =
        await Promise.all([
          fetchMetaOverview(startDate, endDate),
          fetchCampaigns(startDate, endDate),
          fetchAdsets(startDate, endDate),
          fetchAds(startDate, endDate),
        ]);
      console.log("All loaded");

      console.log("overviewData", overviewData);
      console.log("campaignsData", campaignsData);

      setOverview(overviewData.overview || null);
      setCampaigns(campaignsData.campaigns || []);
      setAdsets(adsetsData.adsets || []);
      setAds(adsData.ads || []);
    } catch (error) {
      console.error("Meta Ads Load Error", error);
      console.error("Response:", error.response);
      console.error("Data:", error.response?.data);

      toast.error(
        error.response?.data?.detail || "Failed to load Meta Ads data.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      let range;

      switch (selectedFilter) {
        case "today":
          range = {
            startDate: getPakistanDate(),
            endDate: getPakistanDate(),
          };
          break;

        case "yesterday":
          range = {
            startDate: getPakistanYesterday(),
            endDate: getPakistanYesterday(),
          };
          break;

        case "week": {
          const now = new Date(
            new Date().toLocaleString("en-US", {
              timeZone: "Asia/Karachi",
            }),
          );

          const firstDay = new Date(now);

          firstDay.setDate(now.getDate() - now.getDay());

          range = {
            startDate: firstDay.toISOString().split("T")[0],

            endDate: getPakistanDate(),
          };

          break;
        }

        case "month": {
          const now = new Date(
            new Date().toLocaleString("en-US", {
              timeZone: "Asia/Karachi",
            }),
          );

          const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);

          range = {
            startDate: firstDay.toISOString().split("T")[0],

            endDate: getPakistanDate(),
          };

          break;
        }

        case "all":
          range = getAllTimeRange();
          break;

        case "custom":
          if (appliedStartDate && appliedEndDate) {
            await loadMetaData(
              appliedStartDate.toISOString().split("T")[0],
              appliedEndDate.toISOString().split("T")[0],
            );
          }
          return;

        default:
          range = {
            startDate: getPakistanDate(),
            endDate: getPakistanDate(),
          };
      }

      await loadMetaData(range.startDate, range.endDate);
    };

    fetchData();
  }, [selectedFilter, appliedStartDate, appliedEndDate]);

  const filteredAdsets = adsets.filter(
    (adset) => adset.campaign_id === selectedCampaign,
  );

  const filteredAds = ads.filter((ad) => ad.adset_id === selectedAdset);
  if (loading) {
    return (
      <div className="max-w-[1800px] p-6 animate-pulse">
        <div className="mb-10">
          <div className="h-14 w-80 rounded-xl bg-slate-800 mb-4"></div>
          <div className="h-6 w-96 rounded-xl bg-slate-800"></div>
        </div>

        <div className="flex gap-4 mb-8">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-12 w-36 rounded-2xl bg-slate-800" />
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 mb-12">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="rounded-3xl bg-slate-900 border border-slate-800 p-7 h-[180px]"
            >
              <div className="h-5 w-28 bg-slate-800 rounded mb-8"></div>

              <div className="h-10 w-40 bg-slate-800 rounded"></div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="rounded-3xl bg-slate-900 border border-slate-800 p-7 h-[260px]"
            >
              <div className="h-6 w-40 bg-slate-800 rounded mb-6"></div>

              {[1, 2, 3, 4, 5, 6].map((j) => (
                <div key={j} className="h-4 bg-slate-800 rounded mb-4" />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1800px] p-6">
      {/* HEADER */}

      <div className="mb-10">
        <div
          className="
            flex
            flex-col
            xl:flex-row
            xl:items-center
            xl:justify-between
            gap-6
          "
        >
          <div>
            <h1
              className="
                text-5xl
                font-black
                tracking-tight
                mb-3
                text-white
              "
            >
              Meta Ads
            </h1>

            <p className="text-slate-400 text-xl">
              Advertising intelligence and campaign analytics
            </p>
          </div>

          <div
            className="
              bg-gradient-to-br
              from-slate-900
              to-slate-950
              border
              border-slate-800
              rounded-3xl
              px-8
              py-8
              min-w-[220px]
            "
          >
            <p className="text-slate-400 text-sm mb-2">Active Filter</p>

            <h3
              className="
                text-cyan-400
                font-black
                text-3xl
                capitalize
              "
            >
              {selectedFilter}
            </h3>
          </div>
        </div>
      </div>

      <div
        className="
            flex
            flex-wrap
            gap-4
            mb-8
          "
      >
        <FilterButton
          label="Today"
          active={selectedFilter === "today"}
          onClick={() => {
            setSelectedFilter("today");

            setAppliedStartDate(null);
            setAppliedEndDate(null);
          }}
        />

        <FilterButton
          label="Yesterday"
          active={selectedFilter === "yesterday"}
          onClick={() => {
            setSelectedFilter("yesterday");

            setAppliedStartDate(null);
            setAppliedEndDate(null);
          }}
        />

        <FilterButton
          label="This Week"
          active={selectedFilter === "week"}
          onClick={() => {
            setSelectedFilter("week");

            setAppliedStartDate(null);
            setAppliedEndDate(null);
          }}
        />

        <FilterButton
          label="This Month"
          active={selectedFilter === "month"}
          onClick={() => {
            setSelectedFilter("month");

            setAppliedStartDate(null);
            setAppliedEndDate(null);
          }}
        />

        <FilterButton
          label="All Time"
          active={selectedFilter === "all"}
          onClick={() => {
            setSelectedFilter("all");

            setAppliedStartDate(null);
            setAppliedEndDate(null);
          }}
        />

        <FilterButton
          label="Custom Range"
          active={selectedFilter === "custom"}
          onClick={() => setSelectedFilter("custom")}
        />
      </div>

      {selectedFilter === "custom" && (
        <div
          className="
      flex
      flex-wrap
      items-end
      gap-4
      mb-10
    "
        >
          <div>
            <p className="text-slate-300 mb-3 text-base">Start Date</p>

            <DatePicker
              selected={customStartDate}
              onChange={(date) => setCustomStartDate(date)}
              placeholderText="Select Start Date"
              className="
          bg-[#111C3D]
          border
          border-white/10
          rounded-2xl
          px-4
          py-3
          text-white
          outline-none
          w-[240px]
        "
            />
          </div>

          <div>
            <p className="text-slate-300 mb-3 text-base">End Date</p>

            <DatePicker
              selected={customEndDate}
              onChange={(date) => setCustomEndDate(date)}
              placeholderText="Select End Date"
              className="
          bg-[#111C3D]
          border
          border-white/10
          rounded-2xl
          px-4
          py-3
          text-white
          outline-none
          w-[240px]
        "
            />
          </div>

          <button
            onClick={() => {
              if (!customStartDate || !customEndDate) return;

              setAppliedStartDate(customStartDate);
              setAppliedEndDate(customEndDate);
            }}
            className="
        min-w-[180px]
        px-8
        py-4
        rounded-3xl
        bg-cyan-500
        text-black
        border
        border-cyan-400
        font-bold
        shadow-lg
        shadow-cyan-500/20
      "
          >
            Apply Filter
          </button>
        </div>
      )}

      {/* OVERVIEW */}

      <div className="mb-12">
        <div className="mb-5">
          <h2 className="text-2xl font-bold text-white">Meta Performance</h2>

          <p className="text-slate-400 mt-1">Campaign performance overview</p>
        </div>

        <div
          className="
    grid
    grid-cols-1
    md:grid-cols-2
    xl:grid-cols-3
    gap-5
  "
        >
          <MetaCard
            title="Total Spend"
            value={`Rs ${Number(overview?.spend || 0).toLocaleString()}`}
          />

          <MetaCard
            title="Sales"
            value={overview?.sales || 0}
            color="text-purple-400"
          />

          <MetaCard
            title="Messages"
            value={overview?.instagram_messages || 0}
            color="text-green-400"
          />

          <MetaCard
            title="CTR"
            value={`${overview?.ctr || 0}%`}
            color="text-cyan-400"
          />

          <MetaCard
            title="CPC"
            value={`Rs. ${overview?.cpc || 0}`}
            color="text-yellow-400"
          />
        </div>
      </div>

      {/* CAMPAIGNS */}

      <div className="mb-12">
        <h2 className="text-3xl font-bold mb-6">Campaigns</h2>

        <div
          className="
              grid
              grid-cols-1
              md:grid-cols-2
              xl:grid-cols-3
              gap-5
            "
        >
          {campaigns.map((campaign) => (
            <div
              key={campaign.campaign_id}
              onClick={() => {
                setSelectedCampaign(campaign.campaign_id);

                setSelectedAdset(null);
              }}
              className={`
                cursor-pointer
                bg-gradient-to-br
                from-slate-900
                to-slate-950
                rounded-3xl
                p-7
                border
                transition-all
                hover:-translate-y-1
                hover:shadow-xl
                hover:shadow-cyan-500/10

                ${
                  selectedCampaign === campaign.campaign_id
                    ? "border-cyan-400"
                    : "border-slate-800"
                }
              `}
            >
              <h3 className="font-bold text-lg mb-4">
                {campaign.campaign_name}
              </h3>

              <div className="space-y-2 text-sm">
                <p>
                  Spend:
                  <span className="font-semibold ml-2">
                    Rs. {campaign.spend}
                  </span>
                </p>

                <p>
                  Sales:
                  <span className="font-semibold ml-2">{campaign.sales}</span>
                </p>

                <p>
                  Messages:
                  <span className="font-semibold ml-2">
                    {campaign.instagram_messages}
                  </span>
                </p>

                <p>
                  Leads:
                  <span className="font-semibold ml-2">{campaign.leads}</span>
                </p>

                <p>
                  CTR:
                  <span className="font-semibold ml-2">{campaign.ctr}%</span>
                </p>

                <p>
                  Status:
                  <span className="font-semibold ml-2">{campaign.status}</span>
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ADSETS */}

      {selectedCampaign && (
        <div className="mb-12">
          <h2 className="text-3xl font-bold mb-6">Ad Sets</h2>

          <div
            className="
                grid
                grid-cols-1
                md:grid-cols-2
                xl:grid-cols-3
                gap-5
              "
          >
            {filteredAdsets.map((adset) => (
              <div
                key={adset.adset_id}
                onClick={() => setSelectedAdset(adset.adset_id)}
                className={`
                cursor-pointer
                bg-gradient-to-br
                from-slate-900
                to-slate-950
                rounded-3xl
                p-7
                border
                transition-all
                hover:-translate-y-1
                hover:shadow-xl
                hover:shadow-green-500/10

                ${selectedAdset === adset.adset_id ? "border-green-400" : "border-slate-800"}
              `}
              >
                <h3 className="font-bold text-lg mb-4">{adset.adset_name}</h3>

                <div className="space-y-2 text-sm">
                  <p>
                    Spend:
                    <span className="font-semibold ml-2">
                      Rs. {adset.spend}
                    </span>
                  </p>

                  <p>
                    Sales:
                    <span className="font-semibold ml-2">{adset.sales}</span>
                  </p>

                  <p>
                    Messages:
                    <span className="font-semibold ml-2">
                      {adset.instagram_messages}
                    </span>
                  </p>

                  <p>
                    Leads:
                    <span className="font-semibold ml-2">{adset.leads}</span>
                  </p>

                  <p>
                    CTR:
                    <span className="font-semibold ml-2">{adset.ctr}%</span>
                  </p>

                  <p>
                    Status:
                    <span className="font-semibold ml-2">{adset.status}</span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ADS */}

      {selectedAdset && (
        <div className="mb-12">
          <h2 className="text-3xl font-bold mb-6">Ads</h2>

          <div
            className="
              grid
              grid-cols-1
              md:grid-cols-2
              xl:grid-cols-3
              gap-5
            "
          >
            {filteredAds.map((ad) => (
              <div
                key={ad.ad_id}
                className="
  bg-gradient-to-br
  from-slate-900
  to-slate-950
  rounded-3xl
  p-7
  border
  border-slate-800
  hover:border-cyan-500/30
  hover:-translate-y-1
  hover:shadow-xl
  hover:shadow-cyan-500/10
  transition-all
"
              >
                <h3 className="font-bold text-lg mb-4">{ad.ad_name}</h3>

                <div className="space-y-2 text-sm">
                  <p>
                    Spend:
                    <span className="font-semibold ml-2">Rs. {ad.spend}</span>
                  </p>

                  <p>
                    Sales:
                    <span className="font-semibold ml-2">{ad.sales}</span>
                  </p>

                  <p>
                    Messages:
                    <span className="font-semibold ml-2">
                      {ad.instagram_messages}
                    </span>
                  </p>

                  <p>
                    Leads:
                    <span className="font-semibold ml-2">{ad.leads}</span>
                  </p>

                  <p>
                    CTR:
                    <span className="font-semibold ml-2">{ad.ctr}%</span>
                  </p>

                  <p>
                    CPC:
                    <span className="font-semibold ml-2">Rs. {ad.cpc}</span>
                  </p>

                  <p>
                    Status:
                    <span className="font-semibold ml-2">{ad.status}</span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetaCard({ title, value, color = "" }) {
  return (
    <div
      className="
        bg-gradient-to-br
        from-slate-900
        to-slate-950
        rounded-3xl
        p-7
        border
        border-slate-800
        hover:border-cyan-500/40
        hover:-translate-y-1
        hover:shadow-2xl
        hover:shadow-cyan-500/10
        transition-all
        min-h-[180px]
        flex
        flex-col
        justify-between
      "
    >
      <p className="text-slate-400 text-lg font-medium">{title}</p>

      <h2
        className={`
    text-2xl
xl:text-3xl
    font-black
    mt-4
    break-words
    ${color}
  `}
      >
        {value}
      </h2>
    </div>
  );
}

function FilterButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`
        px-6
        py-3
        rounded-2xl
        border
        transition-all
        font-semibold
        text-lg

        ${
          active
            ? `
              bg-cyan-500
              text-black
              border-cyan-400
              shadow-lg
              shadow-cyan-500/20
            `
            : `
              bg-slate-900
              text-slate-300
              border-slate-800
              hover:border-slate-600
              hover:bg-slate-800
            `
        }
      `}
    >
      {label}
    </button>
  );
}

export default MetaAds;
