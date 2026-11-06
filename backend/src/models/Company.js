const mongoose = require("mongoose");

const companySchema = new mongoose.Schema(
  {
    symbol: {
      type: String,
      required: [true, "Symbol is required"],
      unique: true,
      uppercase: true,
      trim: true,
    },
    name: {
      type: String,
      required: [true, "Company name is required"],
      trim: true,
    },
    category: {
      type: String,
      required: [true, "Category is required"],
      enum: ["Metal", "Mining"],
    },
    subCategory: {
      type: String,
      enum: [
        "Steel",
        "Aluminium",
        "Iron Ore",
        "Coal",
        "Zinc",
        "Copper",
        "Nickel",
        "Silver",
        "Gold",
        "Manganese",
      ],
      default: "Steel",
    },
    exchange: {
      type: String,
      enum: ["NSE", "BSE"],
      default: "NSE",
    },
    isActive: {
      type: Boolean,
      default: true,
    },
    addedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model("Company", companySchema);
