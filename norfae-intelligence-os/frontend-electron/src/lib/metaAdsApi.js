import api from "./api";

export const fetchMetaOverview = async (startDate, endDate) => {
  const response = await api.get("/meta-ads/overview", {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
  });

  return response.data;
};

export const fetchCampaigns = async (startDate, endDate) => {
  const response = await api.get("/meta-ads/campaigns", {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
  });

  return response.data;
};

export const fetchAdsets = async (startDate, endDate) => {
  const response = await api.get("/meta-ads/adsets", {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
  });

  return response.data;
};

export const fetchAds = async (startDate, endDate) => {
  const response = await api.get("/meta-ads/ads", {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
  });

  return response.data;
};

export const fetchMetaTrends = async (startDate, endDate) => {
  const response = await api.get("/meta-ads/trends", {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
  });

  return response.data;
};
