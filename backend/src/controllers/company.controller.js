const Company = require("../models/Company");

exports.getAllCompanies = async (req, res) => {
  try {
    const { category } = req.query;
    const filter = { isActive: true };
    if (category) filter.category = category;

    const companies = await Company.find(filter).sort({ name: 1 });
    res.json(companies);
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.getCompanyById = async (req, res) => {
  try {
    const company = await Company.findById(req.params.id);
    if (!company) {
      return res.status(404).json({ detail: "Company not found" });
    }
    res.json(company);
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.getCompanyBySymbol = async (req, res) => {
  try {
    const company = await Company.findOne({ symbol: req.params.symbol.toUpperCase() });
    if (!company) {
      return res.status(404).json({ detail: "Company not found" });
    }
    res.json(company);
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.addCompany = async (req, res) => {
  try {
    const { symbol, name, category, subCategory, exchange } = req.body;

    const existing = await Company.findOne({ symbol: symbol.toUpperCase() });
    if (existing) {
      return res.status(400).json({ detail: "Company with this symbol already exists" });
    }

    const company = await Company.create({
      symbol: symbol.toUpperCase(),
      name,
      category,
      subCategory,
      exchange,
      addedBy: req.user._id,
    });

    res.status(201).json(company);
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.updateCompany = async (req, res) => {
  try {
    const company = await Company.findByIdAndUpdate(req.params.id, req.body, {
      new: true,
      runValidators: true,
    });
    if (!company) {
      return res.status(404).json({ detail: "Company not found" });
    }
    res.json(company);
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.deleteCompany = async (req, res) => {
  try {
    const company = await Company.findByIdAndUpdate(
      req.params.id,
      { isActive: false },
      { new: true }
    );
    if (!company) {
      return res.status(404).json({ detail: "Company not found" });
    }
    res.json({ detail: "Company deleted successfully" });
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.seedCompanies = async (req, res) => {
  try {
    const defaultCompanies = [
      { symbol: "HINDALCO.NS", name: "Hindalco Industries", category: "Metal", subCategory: "Aluminium" },
      { symbol: "TATASTEEL.NS", name: "Tata Steel", category: "Metal", subCategory: "Steel" },
      { symbol: "VEDL.NS", name: "Vedanta Limited", category: "Metal", subCategory: "Zinc" },
      { symbol: "COALINDIA.NS", name: "Coal India", category: "Mining", subCategory: "Coal" },
      { symbol: "NMDC.NS", name: "NMDC Limited", category: "Mining", subCategory: "Iron Ore" },
      { symbol: "JSWSTEEL.NS", name: "JSW Steel", category: "Metal", subCategory: "Steel" },
      { symbol: "NATIONALUM.NS", name: "NALCO", category: "Metal", subCategory: "Aluminium" },
      { symbol: "HINDZINC.NS", name: "Hindustan Zinc", category: "Metal", subCategory: "Zinc" },
      { symbol: "SAIL.NS", name: "Steel Authority of India", category: "Metal", subCategory: "Steel" },
      { symbol: "JINDALSTEL.NS", name: "Jindal Steel & Power", category: "Metal", subCategory: "Steel" },
    ];

    let created = 0;
    let skipped = 0;

    for (const comp of defaultCompanies) {
      const exists = await Company.findOne({ symbol: comp.symbol });
      if (!exists) {
        await Company.create({ ...comp, addedBy: req.user._id });
        created++;
      } else {
        skipped++;
      }
    }

    res.json({ detail: `Seeded: ${created} created, ${skipped} skipped` });
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};
