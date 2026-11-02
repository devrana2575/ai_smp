const express = require("express");
const router = express.Router();
const companyController = require("../controllers/company.controller");
const { auth, adminOnly } = require("../middleware/auth");

router.get("/", auth, companyController.getAllCompanies);
router.get("/symbol/:symbol", auth, companyController.getCompanyBySymbol);
router.get("/:id", auth, companyController.getCompanyById);
router.post("/", auth, adminOnly, companyController.addCompany);
router.put("/:id", auth, adminOnly, companyController.updateCompany);
router.delete("/:id", auth, adminOnly, companyController.deleteCompany);
router.post("/seed", auth, companyController.seedCompanies);

module.exports = router;
