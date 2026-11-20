export const getPakistanDate = () => {
  return new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Karachi",
  });
};

export const getPakistanDateTime = () => {
  return new Date().toLocaleString("en-US", {
    timeZone: "Asia/Karachi",
  });
};
