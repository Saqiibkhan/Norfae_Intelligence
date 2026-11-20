const getPakistanDate = () =>
  new Date(
    new Date().toLocaleString("en-US", {
      timeZone: "Asia/Karachi",
    }),
  );

export const formatPakistanDate = (date) =>
  date.toLocaleDateString("en-CA", {
    timeZone: "Asia/Karachi",
  });

const getPakistanDateString = (date = new Date()) =>
  date.toLocaleDateString("en-CA", {
    timeZone: "Asia/Karachi",
  });

export const getTodayRange = () => {
  const today = getPakistanDateString();

  return {
    startDate: today,
    endDate: today,
  };
};

export const getYesterdayRange = () => {
  const yesterday = getPakistanDate();

  yesterday.setDate(yesterday.getDate() - 1);

  return {
    startDate: getPakistanDateString(yesterday),
    endDate: getPakistanDateString(yesterday),
  };
};

export const getWeekRange = () => {
  const now = getPakistanDate();

  const firstDay = new Date(now);

  const day = now.getDay() || 7;

  firstDay.setDate(now.getDate() - day + 1);

  return {
    startDate: getPakistanDateString(firstDay),
    endDate: getPakistanDateString(now),
  };
};

export const getMonthRange = () => {
  const now = getPakistanDate();

  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);

  return {
    startDate: getPakistanDateString(firstDay),
    endDate: getPakistanDateString(now),
  };
};

export const getAllTimeRange = () => {
  return {
    startDate: null,
    endDate: null,
  };
};
