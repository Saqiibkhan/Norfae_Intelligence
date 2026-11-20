export default function TopCampaignsTable({ campaigns }) {
  return (
    <div className="bg-slate-900 rounded-3xl p-6 border border-slate-800">
      <h3 className="text-xl font-bold mb-6">Top Campaigns</h3>

      <table className="w-full">
        <thead>
          <tr>
            <th className="text-left pb-4">Campaign</th>

            <th className="text-left pb-4">Spend</th>

            <th className="text-left pb-4">Messages</th>
          </tr>
        </thead>

        <tbody>
          {campaigns.map((c) => (
            <tr key={c.campaign_id} className="border-t border-slate-800">
              <td className="py-3">{c.campaign_name}</td>

              <td>Rs. {c.spend}</td>

              <td>{c.instagram_messages}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
