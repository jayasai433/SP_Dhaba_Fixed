import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import BusinessProfilePane from "@/pages/settings/BusinessProfilePane";
import NamedListPane from "@/pages/settings/NamedListPane";
import UsersPane from "@/pages/settings/UsersPane";
import StaffPane from "@/pages/settings/StaffPane";
import SupplierPane from "@/pages/settings/SupplierPane";
import WhatsAppPane from "@/pages/settings/WhatsAppPane";
import ReorderPane from "@/pages/settings/ReorderPane";

const TABS = [
  ["business", "Business"],
  ["categories", "Categories"],
  ["expense-cats", "Expense Cats"],
  ["units", "Units"],
  ["users", "Users"],
  ["staff", "Payroll Staff"],
  ["suppliers", "Suppliers"],
  ["whatsapp", "WhatsApp"],
  ["reorder", "Reorder Levels"],
];

export default function Settings() {
  return (
    <div className="space-y-6 animate-fade-up" data-testid="settings-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Admin</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-600 text-sm mt-1">Everything you might need to change — no developer needed.</p>
      </div>

      <Tabs defaultValue="business" className="w-full">
        <TabsList className="bg-orange-50 p-1 rounded-full overflow-x-auto flex w-full max-w-full">
          {TABS.map(([v, label]) => (
            <TabsTrigger key={v} value={v} data-testid={`settings-tab-${v}`} className="rounded-full">{label}</TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="business"><BusinessProfilePane /></TabsContent>
        <TabsContent value="categories"><NamedListPane apiPath="/categories" label="Category" testid="categories" /></TabsContent>
        <TabsContent value="expense-cats"><NamedListPane apiPath="/expense-categories" label="Expense Category" testid="expense-cats" /></TabsContent>
        <TabsContent value="units"><NamedListPane apiPath="/units" label="Unit" testid="units" /></TabsContent>
        <TabsContent value="users"><UsersPane /></TabsContent>
        <TabsContent value="staff"><StaffPane /></TabsContent>
        <TabsContent value="suppliers"><SupplierPane /></TabsContent>
        <TabsContent value="whatsapp"><WhatsAppPane /></TabsContent>
        <TabsContent value="reorder"><ReorderPane /></TabsContent>
      </Tabs>
    </div>
  );
}
