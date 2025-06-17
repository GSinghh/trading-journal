import { useRef, useState } from "react";
import { Button } from "./ui/button";

const Import_Trade_Button = () => {
    const API_ENDPOINT = "https://httpbin.org/post";

    const fileInputRef = useRef<HTMLInputElement>(null);
    const [file, setFile] = useState<File | null>(null);
    const [status, setStatus] = useState("");

    const onButtonClick = () => {
        fileInputRef.current?.click();
    };

    const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.length) {
            const file = e.target.files[0];
            if (!file) {
                console.error("Error while uploading file");
                return;
            } else {
                setFile(file);
                console.log("File is set: ", file.name);
                const formData = new FormData();
                formData.append("trades", file, file.name);
                try {
                    const response = await fetch(API_ENDPOINT, {
                        method: "POST",
                        headers: {
                            // "Authorization": `Bearer ${token}`,
                        },
                        body: formData,
                    });
                    if (!response.ok) {
                        const err = await response.text();
                        throw new Error(err || response.statusText);
                    }
                    const data = await response.json();
                    setStatus("In Progress");
                    console.log("Response from website: ", data);
                } catch (e: any) {
                    console.log("Error: ", e);
                    setStatus("Upload Failed: " + e.message);
                }
            }
        }
    };

    return (
        <>
            <Button onClick={onButtonClick} className="bg-gray-100 text-black">
                Import Trades
                <input
                    type="file"
                    accept=".csv"
                    ref={fileInputRef}
                    onChange={onFileChange}
                    style={{ display: "none" }}
                />
            </Button>
        </>
    );
};

export default Import_Trade_Button;
