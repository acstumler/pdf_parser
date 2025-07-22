import React, { useState, useEffect, useRef, useContext } from "react";
import axios from "axios";
import { TransactionContext } from "../context/TransactionContext";

const PARSER_ENDPOINT = "https://lighthouse-pdf-parser.onrender.com/parse-pdf/";

const UploadParser = () => {
  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("Drop files here or click to upload");
  const inputRef = useRef(null);
  const { addParsedTransactions, addUploadLogEntry } = useContext(TransactionContext);

  useEffect(() => {
    const savedTransactions = localStorage.getItem("lumi_transactions");
    const savedUploadLog = localStorage.getItem("lumi_uploadLog");
    if (savedTransactions) addParsedTransactions(JSON.parse(savedTransactions));
    if (savedUploadLog) addUploadLogEntry(JSON.parse(savedUploadLog));
  }, []);

  const handleFileUpload = async (file) => {
    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploadStatus("Uploading...");
      const response = await axios.post(PARSER_ENDPOINT, formData);
      const { transactions, source, count } = response.data;

      if (transactions && transactions.length > 0) {
        addParsedTransactions(transactions);
        addUploadLogEntry([{ date: new Date().toLocaleString(), file: file.name, source, count }]);
        setUploadStatus("Upload complete!");
      } else {
        setUploadStatus("No transactions found.");
      }
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadStatus("Upload failed");
    } finally {
      setTimeout(() => setUploadStatus("Drop files here or click to upload"), 2000);
    }
  };

  const handleChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) handleFileUpload(files[0]);
    inputRef.current.value = null; // clear input
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className={`upload-drop-zone ${dragActive ? "active" : ""}`}
      style={{
        border: "2px dashed #aaa",
        borderRadius: "8px",
        padding: "1.5rem",
        textAlign: "center",
        background: dragActive ? "#f9f9f9" : "transparent",
        transition: "background 0.3s ease"
      }}
    >
      <input
        type="file"
        accept=".pdf"
        ref={inputRef}
        onChange={handleChange}
        style={{ display: "none" }}
      />
      <button onClick={() => inputRef.current.click()}>Choose File</button>
      <p style={{ marginTop: "0.5rem", color: uploadStatus.includes("failed") ? "red" : "#777" }}>
        {uploadStatus}
      </p>
    </div>
  );
};

export default UploadParser;
